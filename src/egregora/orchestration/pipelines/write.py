"""Write pipeline orchestration - executes the complete write workflow.

This module orchestrates the high-level flow for the 'write' command, coordinating:
- Input adapter selection and parsing
- Privacy and enrichment stages
- Content generation with WriterWorker
- Command processing and announcement generation
- Profile generation (Egregora writing ABOUT authors)
- Background task processing
"""

from __future__ import annotations

import json
import logging
import math
import os
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import google.generativeai as genai
import ibis
import ibis.common.exceptions
from rich.console import Console
from rich.panel import Panel

from egregora.agents.avatar import AvatarContext, process_avatar_commands
from egregora.agents.banner.worker import BannerWorker
from egregora.agents.commands import command_to_announcement, filter_commands
from egregora.agents.commands import extract_commands as extract_commands_list
from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker, schedule_enrichment
from egregora.agents.profile.generator import generate_profile_posts
from egregora.agents.profile.worker import ProfileWorker
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.writer import WindowProcessingParams, write_posts_for_window
from egregora.config import RuntimeContext, load_egregora_config
from egregora.config.settings import EgregoraConfig, parse_date_arg, validate_timezone
from egregora.constants import WindowUnit
from egregora.data_primitives.document import OutputSink, UrlContext
from egregora.database import initialize_database
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.task_store import TaskStore
from egregora.database.utils import resolve_db_uri
from egregora.input_adapters import ADAPTER_REGISTRY
from egregora.input_adapters.whatsapp.commands import extract_commands, filter_egregora_messages
from egregora.knowledge.profiles import filter_opted_out_authors, process_commands
from egregora.llm.api_keys import get_google_api_keys, validate_gemini_api_key
from egregora.llm.exceptions import AllModelsExhaustedError
from egregora.llm.rate_limit import init_rate_limiter
from egregora.llm.usage import UsageTracker
from egregora.ops.media import process_media_for_window
from egregora.ops.taxonomy import generate_semantic_taxonomy
from egregora.orchestration.cache import PipelineCache
from egregora.orchestration.context import PipelineConfig, PipelineContext, PipelineRunParams, PipelineState
from egregora.orchestration.factory import PipelineFactory
from egregora.output_adapters import create_default_output_registry
from egregora.output_adapters.mkdocs import MkDocsPaths
from egregora.output_adapters.mkdocs.scaffolding import MkDocsSiteScaffolder
from egregora.rag import index_documents, reset_backend
from egregora.transformations import (
    Window,
    WindowConfig,
    create_windows,
    split_window_into_n_parts,
)

try:
    import dotenv
except ImportError:
    dotenv = None

if TYPE_CHECKING:
    import ibis.expr.types as ir


logger = logging.getLogger(__name__)
console = Console()
__all__ = ["WhatsAppProcessOptions", "WriteCommandOptions", "process_whatsapp_export", "run", "run_cli_flow"]

MIN_WINDOWS_WARNING_THRESHOLD = 5


@dataclass
class WriteCommandOptions:
    """Options for the write command."""

    input_file: Path
    source: str
    output: Path
    step_size: int
    step_unit: WindowUnit
    overlap: float
    enable_enrichment: bool
    from_date: str | None
    to_date: str | None
    timezone: str | None
    model: str | None
    max_prompt_tokens: int
    use_full_context_window: bool
    max_windows: int | None
    resume: bool
    refresh: str | None
    force: bool
    debug: bool


@dataclass(frozen=True)
class WhatsAppProcessOptions:
    """Runtime overrides for :func:`process_whatsapp_export`."""

    output_dir: Path = Path("output")
    step_size: int = 100
    step_unit: str = "messages"
    overlap_ratio: float = 0.2
    enable_enrichment: bool = True
    from_date: date_type | None = None
    to_date: date_type | None = None
    timezone: str | ZoneInfo | None = None
    gemini_api_key: str | None = None
    model: str | None = None
    batch_threshold: int = 10
    max_prompt_tokens: int = 100_000
    use_full_context_window: bool = False
    client: genai.GenerativeModel | None = None
    refresh: str | None = None


def _load_dotenv_if_available(output_dir: Path) -> None:
    if dotenv:
        dotenv.load_dotenv(output_dir / ".env")
        dotenv.load_dotenv()  # Check CWD as well


# TODO: [Taskmaster] Refactor API key validation for clarity and separation of concerns
def _validate_api_key(output_dir: Path) -> None:
    """Validate that API key is set and valid."""
    skip_validation = os.getenv("EGREGORA_SKIP_API_KEY_VALIDATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }

    api_keys = get_google_api_keys()
    if not api_keys:
        _load_dotenv_if_available(output_dir)
        api_keys = get_google_api_keys()

    if not api_keys:
        console.print("[red]Error: GOOGLE_API_KEY (or GEMINI_API_KEY) environment variable not set[/red]")
        console.print(
            "Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable with your Google Gemini API key"
        )
        console.print("You can also create a .env file in the output directory or current directory.")
        raise SystemExit(1)

    if skip_validation:
        if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = api_keys[0]
        return

    console.print("[cyan]Validating Gemini API key...[/cyan]")
    validation_errors: list[str] = []
    for key in api_keys:
        try:
            validate_gemini_api_key(key)
            if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
                os.environ["GOOGLE_API_KEY"] = key
            console.print("[green]✓ API key validated successfully[/green]")
            return
        except ValueError as e:
            validation_errors.append(str(e))
        except ImportError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise SystemExit(1) from e

    joined = "\n\n".join(validation_errors)
    console.print(f"[red]Error: {joined}[/red]")
    raise SystemExit(1)


def _prepare_write_config(
    options: WriteCommandOptions, from_date_obj: date_type | None, to_date_obj: date_type | None
) -> Any:
    """Prepare Egregora configuration from options."""
    base_config = load_egregora_config(options.output)
    models_update: dict[str, str] = {}
    if options.model:
        models_update = {
            "writer": options.model,
            "enricher": options.model,
            "enricher_vision": options.model,
            "ranking": options.model,
            "editor": options.model,
        }
    return base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "step_size": options.step_size,
                    "step_unit": options.step_unit,
                    "overlap_ratio": options.overlap,
                    "timezone": options.timezone,
                    "from_date": from_date_obj.isoformat() if from_date_obj else None,
                    "to_date": to_date_obj.isoformat() if to_date_obj else None,
                    "max_prompt_tokens": options.max_prompt_tokens,
                    "use_full_context_window": options.use_full_context_window,
                    "max_windows": options.max_windows,
                    "checkpoint_enabled": options.resume,
                }
            ),
            "enrichment": base_config.enrichment.model_copy(update={"enabled": options.enable_enrichment}),
            "rag": base_config.rag,
            **({"models": base_config.models.model_copy(update=models_update)} if models_update else {}),
        },
    )


def _resolve_write_options(
    input_file: Path,
    options_json: str | None,
    cli_defaults: dict[str, Any],
) -> WriteCommandOptions:
    """Merge CLI options with JSON options and defaults."""
    # Start with CLI values as base
    defaults = cli_defaults.copy()

    if options_json:
        try:
            overrides = json.loads(options_json)
            # Update with JSON overrides, converting enums if strings
            for k, v in overrides.items():
                if k == "step_unit" and isinstance(v, str):
                    defaults[k] = WindowUnit(v)
                elif k == "output" and isinstance(v, str):
                    defaults[k] = Path(v)
                else:
                    defaults[k] = v
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing options JSON: {e}[/red]")
            raise SystemExit(1) from e

    return WriteCommandOptions(input_file=input_file, **defaults)


def _resolve_sources_to_run(source: str | None, config: EgregoraConfig) -> list[tuple[str, str]]:
    """Resolve which sources to run based on CLI argument and config.

    Args:
        source: Source key, source type, or None
        config: Egregora configuration

    Returns:
        List of (source_key, source_type) tuples to process

    Raises:
        SystemExit: If source is unknown

    """
    # If source is explicitly provided
    if source is not None:
        # Check if it's a source key
        if source in config.site.sources:
            source_config = config.site.sources[source]
            return [(source, source_config.adapter)]

        # Check if it's a source type (adapter name) - find first matching source
        for key, src_config in config.site.sources.items():
            if src_config.adapter == source:
                return [(key, source)]

        # Unknown source
        available_keys = ", ".join(config.site.sources.keys())
        available_types = ", ".join({s.adapter for s in config.site.sources.values()})
        console.print(
            f"[red]Error: Unknown source '{source}'.[/red]\n"
            f"Available source keys: {available_keys}\n"
            f"Available source types: {available_types}"
        )
        raise SystemExit(1)

    # source is None - use default or run all
    if config.site.default_source is None:
        # Run all configured sources
        return [(key, src.adapter) for key, src in config.site.sources.items()]

    # Use default source
    default_key = config.site.default_source
    if default_key not in config.site.sources:
        console.print(f"[red]Error: default_source '{default_key}' not found in configured sources.[/red]")
        raise SystemExit(1)

    return [(default_key, config.site.sources[default_key].adapter)]


# TODO: [Taskmaster] Refactor validation logic into separate functions
def run_cli_flow(
    input_file: Path,
    *,
    output: Path = Path("site"),
    source: str | None = None,
    step_size: int = 100,
    step_unit: WindowUnit = WindowUnit.MESSAGES,
    overlap: float = 0.0,
    enable_enrichment: bool = True,
    from_date: str | None = None,
    to_date: str | None = None,
    timezone: str | None = None,
    model: str | None = None,
    max_prompt_tokens: int = 400000,
    use_full_context_window: bool = False,
    max_windows: int | None = None,
    resume: bool = True,
    refresh: str | None = None,
    force: bool = False,
    debug: bool = False,
    options: str | None = None,
    smoke_test: bool = False,
) -> None:
    """Execute the write flow from CLI arguments.

    Args:
        source: Can be a source type (e.g., "whatsapp"), a source key from config, or None.
                If None, will use default_source from config, or run all sources if default is None.

    """
    cli_values = {
        "source": source,
        "output": output,
        "step_size": step_size,
        "step_unit": step_unit,
        "overlap": overlap,
        "enable_enrichment": enable_enrichment,
        "from_date": from_date,
        "to_date": to_date,
        "timezone": timezone,
        "model": model,
        "max_prompt_tokens": max_prompt_tokens,
        "use_full_context_window": use_full_context_window,
        "max_windows": max_windows,
        "resume": resume,
        "refresh": refresh,
        "force": force,
        "debug": debug,
    }

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    from_date_obj, to_date_obj = None, None
    if from_date:
        try:
            from_date_obj = parse_date_arg(from_date, "from_date")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1) from e
    if to_date:
        try:
            to_date_obj = parse_date_arg(to_date, "to_date")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1) from e

    if timezone:
        try:
            validate_timezone(timezone)
            console.print(f"[green]Using timezone: {timezone}[/green]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1) from e

    output_dir = output.expanduser().resolve()

    config_path = output_dir / ".egregora.toml"

    if not config_path.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Initializing site in %s", output_dir)
        scaffolder = MkDocsSiteScaffolder()
        scaffolder.scaffold_site(output_dir, site_name=output_dir.name)

    _validate_api_key(output_dir)

    # Load config to determine sources
    base_config = load_egregora_config(output_dir)

    # Determine which sources to run
    sources_to_run = _resolve_sources_to_run(source, base_config)

    # Process each source
    for source_key, source_type in sources_to_run:
        # Prepare options with current source
        parsed_options = _resolve_write_options(
            input_file=input_file,
            options_json=options,
            cli_defaults={**cli_values, "source": source_type},
        )

        egregora_config = _prepare_write_config(parsed_options, from_date_obj, to_date_obj)

        runtime = RuntimeContext(
            output_dir=output_dir,
            input_file=parsed_options.input_file,
            model_override=parsed_options.model,
            debug=parsed_options.debug,
        )

        try:
            console.print(
                Panel(
                    f"[cyan]Source:[/cyan] {source_type} (key: {source_key})\n[cyan]Input:[/cyan] {parsed_options.input_file}\n[cyan]Output:[/cyan] {output_dir}\n[cyan]Windowing:[/cyan] {parsed_options.step_size} {parsed_options.step_unit.value}",
                    title="⚙️  Egregora Pipeline",
                    border_style="cyan",
                )
            )
            run_params = PipelineRunParams(
                output_dir=runtime.output_dir,
                config=egregora_config,
                source_type=source_type,
                source_key=source_key,
                input_path=runtime.input_file,
                refresh="all" if parsed_options.force else parsed_options.refresh,
                smoke_test=smoke_test,
            )
            run(run_params)
            console.print(f"[green]Processing completed successfully for source '{source_key}'.[/green]")
        except AllModelsExhaustedError as e:
            # Re-raise this specific error so the 'demo' command can catch it
            raise e
        except Exception as e:
            console.print_exception(show_locals=False)
            console.print(f"[red]Pipeline failed for source '{source_key}': {e}[/]")
            raise SystemExit(1) from e


def process_whatsapp_export(
    zip_path: Path,
    *,
    options: WhatsAppProcessOptions | None = None,
) -> dict[str, dict[str, list[str]]]:
    """High-level helper for processing WhatsApp ZIP exports using :func:`run`."""
    opts = options or WhatsAppProcessOptions()
    output_dir = opts.output_dir.expanduser().resolve()

    if opts.gemini_api_key:
        os.environ["GOOGLE_API_KEY"] = opts.gemini_api_key

    base_config = load_egregora_config(output_dir)

    # Apply CLI model override to all text generation models if provided
    models_update = {}
    if opts.model:
        models_update = {
            "writer": opts.model,
            "enricher": opts.model,
            "enricher_vision": opts.model,
            "ranking": opts.model,
            "editor": opts.model,
        }

    egregora_config = base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "step_size": opts.step_size,
                    "step_unit": opts.step_unit,
                    "overlap_ratio": opts.overlap_ratio,
                    "timezone": str(opts.timezone) if opts.timezone else None,
                    "from_date": opts.from_date.isoformat() if opts.from_date else None,
                    "to_date": opts.to_date.isoformat() if opts.to_date else None,
                    "batch_threshold": opts.batch_threshold,
                    "max_prompt_tokens": opts.max_prompt_tokens,
                    "use_full_context_window": opts.use_full_context_window,
                }
            ),
            "enrichment": base_config.enrichment.model_copy(update={"enabled": opts.enable_enrichment}),
            # RAG settings: no runtime overrides needed (uses config from .egregora/config.yml)
            "rag": base_config.rag,
            **({"models": base_config.models.model_copy(update=models_update)} if models_update else {}),
        },
    )

    run_params = PipelineRunParams(
        output_dir=output_dir,
        config=egregora_config,
        source_type="whatsapp",
        input_path=zip_path,
        client=opts.client,
        refresh=opts.refresh,
    )

    return run(run_params)


@dataclass
class PreparedPipelineData:
    """Artifacts produced during dataset preparation."""

    messages_table: ir.Table
    windows_iterator: Iterator[Window]
    checkpoint_path: Path
    context: PipelineContext
    enable_enrichment: bool
    embedding_model: str


@dataclass
class Conversation:
    """A conversation window prepared for processing (ETL completed)."""

    window: Window
    messages_table: ir.Table
    media_mapping: dict[str, Any]
    context: PipelineContext
    adapter_info: tuple[str, str]
    depth: int = 0


def perform_enrichment(
    context: PipelineContext,
    window_table: ir.Table,
    media_mapping: dict[str, Any],
    override_config: Any | None = None,
) -> ir.Table:
    """Execute enrichment for a window's table."""
    enrichment_context = EnrichmentRuntimeContext(
        cache=context.cache.enrichment,
        output_sink=context.output_sink,
        site_root=context.site_root,
        usage_tracker=context.usage_tracker,
        pii_prevention=None,
        task_store=context.task_store,
    )

    schedule_enrichment(
        window_table,
        media_mapping,
        override_config or context.config.enrichment,
        enrichment_context,
        run_id=context.run_id,
    )

    # Execute enrichment worker immediately (synchronous for now in pipeline)
    # The worker consumes tasks from the store until empty
    with EnrichmentWorker(context, enrichment_config=override_config) as worker:
        while True:
            processed = worker.run()
            if processed == 0:
                break

    return window_table


def _extract_adapter_info(ctx: PipelineContext) -> tuple[str, str]:
    """Extract content summary and generation instructions from adapter."""
    adapter = getattr(ctx, "adapter", None)
    if adapter is None:
        return "", ""

    summary: str | None = ""
    try:
        summary = getattr(adapter, "content_summary", "")
        if callable(summary):
            summary = summary()
    except (AttributeError, TypeError) as exc:
        logger.debug("Adapter %s failed to provide content_summary: %s", adapter, exc)
        summary = ""

    instructions: str | None = ""
    try:
        instructions = getattr(adapter, "generation_instructions", "")
        if callable(instructions):
            instructions = instructions()
    except (AttributeError, TypeError) as exc:
        logger.warning("Failed to evaluate adapter generation instructions: %s", exc)
        instructions = ""

    return (summary or "").strip(), (instructions or "").strip()


def _calculate_max_window_size(config: EgregoraConfig) -> int:
    """Calculate maximum window size based on LLM context window."""
    use_full_window = getattr(config.pipeline, "use_full_context_window", False)
    # Corresponds to a 1M token context window, expressed in characters
    full_context_window_size = 1_048_576

    max_tokens = full_context_window_size if use_full_window else config.pipeline.max_prompt_tokens

    # TODO: [Taskmaster] Externalize hardcoded configuration values.
    avg_tokens_per_message = 5
    buffer_ratio = 0.8
    return int((max_tokens * buffer_ratio) / avg_tokens_per_message)


def get_pending_conversations(dataset: PreparedPipelineData) -> Iterator[Conversation]:
    """Yield prepared conversations ready for processing.

    This generator handles:
    1. Window iteration
    2. Size validation and splitting (heuristic)
    3. Media processing
    4. Enrichment
    5. Command extraction (partial)
    """
    ctx = dataset.context
    max_window_size = _calculate_max_window_size(ctx.config)

    # Use a queue to handle splitting
    # Each item is (window, depth)
    queue: deque[tuple[Window, int]] = deque([(w, 0) for w in dataset.windows_iterator])

    max_depth = 5
    min_window_size = 5

    processed_count = 0
    max_windows = getattr(ctx.config.pipeline, "max_windows", None)
    if max_windows == 0:
        max_windows = None

    while queue:
        if max_windows is not None and processed_count >= max_windows:
            logger.info("Reached max_windows limit (%d). Stopping.", max_windows)
            break

        window, depth = queue.popleft()

        # Heuristic splitting check
        if window.size > max_window_size and depth < max_depth:
            # Too big, split immediately based on heuristic
            logger.info(
                "Window %d too large (%d > %d), splitting...",
                window.window_index,
                window.size,
                max_window_size,
            )
            num_splits = max(2, math.ceil(window.size / max_window_size))
            split_windows = split_window_into_n_parts(window, num_splits)
            # Add back to front of queue
            queue.extendleft(reversed([(w, depth + 1) for w in split_windows]))
            continue

        if window.size < min_window_size and depth > 0:
            logger.warning("Window too small after split (%d messages), attempting anyway", window.size)

        # ETL Step 1: Media Processing
        output_sink = ctx.output_sink
        if output_sink is None:
            # Should not happen if dataset is prepared correctly
            msg = "Output sink not initialized"
            raise ValueError(msg)

        url_context = ctx.url_context or UrlContext()
        window_table_processed, media_mapping = process_media_for_window(
            window_table=window.table,
            adapter=ctx.adapter,
            url_convention=output_sink.url_convention,
            url_context=url_context,
            zip_path=ctx.input_path,
        )

        # Persist media if enrichment disabled (otherwise enrichment handles it/updates it)
        if media_mapping and not dataset.enable_enrichment:
            for media_doc in media_mapping.values():
                try:
                    output_sink.persist(media_doc)
                except Exception as e:
                    logger.exception("Failed to write media file: %s", e)

        # ETL Step 2: Enrichment
        if dataset.enable_enrichment:
            enriched_table = perform_enrichment(ctx, window_table_processed, media_mapping)
        else:
            enriched_table = window_table_processed

        # Prepare metadata
        adapter_info = _extract_adapter_info(ctx)

        yield Conversation(
            window=window,
            messages_table=enriched_table,
            media_mapping=media_mapping,
            context=ctx,
            adapter_info=adapter_info,
            depth=depth,
        )
        processed_count += 1


def process_item(conversation: Conversation) -> dict[str, dict[str, list[str]]]:
    """Execute the agent on an isolated conversation item."""
    ctx = conversation.context
    output_sink = ctx.output_sink

    # Extract commands (ETL/Processing boundary - commands are side effects)
    # We do this here or in generator? Generator does "data prep".
    # Commands might generate announcements which is "output".
    # But filtering commands from input to writer is "prep".

    # Convert table to list
    try:
        executed = conversation.messages_table.execute()
        if hasattr(executed, "to_pylist"):
            messages_list = executed.to_pylist()
        elif hasattr(executed, "to_dict"):
            messages_list = executed.to_dict(orient="records")
        else:
            messages_list = []
    except (AttributeError, TypeError):
        try:
            messages_list = conversation.messages_table.to_pylist()
        except (AttributeError, TypeError):
            messages_list = (
                conversation.messages_table if isinstance(conversation.messages_table, list) else []
            )

    # Handle commands (Announcements)
    command_messages = extract_commands_list(messages_list)
    announcements_generated = 0
    if command_messages:
        for cmd_msg in command_messages:
            try:
                announcement = command_to_announcement(cmd_msg)
                output_sink.persist(announcement)
                announcements_generated += 1
            except Exception as exc:
                logger.exception("Failed to generate announcement: %s", exc)

    clean_messages_list = filter_commands(messages_list)

    # Prepare Resources
    resources = PipelineFactory.create_writer_resources(ctx)

    params = WindowProcessingParams(
        table=conversation.messages_table,
        messages=clean_messages_list,
        window_start=conversation.window.start_time,
        window_end=conversation.window.end_time,
        resources=resources,
        config=ctx.config,
        cache=ctx.cache,
        adapter_content_summary=conversation.adapter_info[0],
        adapter_generation_instructions=conversation.adapter_info[1],
        run_id=str(ctx.run_id) if ctx.run_id else None,
        smoke_test=ctx.state.smoke_test,
    )

    # EXECUTE WRITER
    # Note: We don't handle PromptTooLargeError here because we rely on heuristic splitting
    # in the generator. If it fails here, it fails.
    writer_result = write_posts_for_window(params)
    posts = writer_result.get("posts", [])
    profiles = writer_result.get("profiles", [])

    # Warn if writer processed messages but generated no posts
    if not posts and clean_messages_list:
        logger.warning(
            "⚠️ Writer agent processed %d messages but generated no posts for window %s. "
            "Check if write_post_tool was called by the agent.",
            len(clean_messages_list),
            f"{conversation.window.start_time:%Y-%m-%d %H:%M}",
        )

    # Persist generated posts
    # The writer agent returns documents (strings if pending).
    # Pending posts are handled by background worker?
    # The original runner logic didn't explicitly persist posts returned by `write_posts_for_window`.
    # Let's check `write_posts_for_window` in `src/egregora/agents/writer.py`.
    # It seems `write_posts_for_window` returns paths or IDs, and persistence happens inside tools.
    # However, `generate_profile_posts` returns Document objects that need persistence.
    # If `posts` contains Document objects, we should persist them.
    for post in posts:
        if hasattr(post, "document_id"):  # Is a Document
            try:
                output_sink.persist(post)
            except Exception as exc:
                logger.exception("Failed to persist post: %s", exc)

    # EXECUTE PROFILE GENERATOR
    window_date = conversation.window.start_time.strftime("%Y-%m-%d")
    try:
        profile_docs = generate_profile_posts(ctx=ctx, messages=clean_messages_list, window_date=window_date)
        for profile_doc in profile_docs:
            try:
                output_sink.persist(profile_doc)
                profiles.append(profile_doc.document_id)
            except Exception as exc:
                logger.exception("Failed to persist profile: %s", exc)
    except Exception as exc:
        logger.exception("Failed to generate profile posts: %s", exc)

    # Process background tasks (Banner, etc)
    # We can do it per item or once at end. The prompt says "Execute agent on isolated item".
    # Background tasks are usually global or batched.
    # We will trigger them here to ensure "isolated item" processing is complete.
    process_background_tasks(ctx)

    # Logging
    window_label = f"{conversation.window.start_time:%Y-%m-%d %H:%M} to {conversation.window.end_time:%H:%M}"
    logger.info(
        "  [green]✔ Generated[/] %d posts, %d profiles, %d announcements for %s",
        len(posts),
        len(profiles),
        announcements_generated,
        window_label,
    )

    return {window_label: {"posts": posts, "profiles": profiles}}


def process_background_tasks(ctx: PipelineContext) -> None:
    """Process pending background tasks."""
    if not hasattr(ctx, "task_store") or not ctx.task_store:
        return

    banner_worker = BannerWorker(ctx)
    banner_worker.run()

    profile_worker = ProfileWorker(ctx)
    profile_worker.run()

    # Enrichment is already done in generator, but if new tasks were added:
    if ctx.config.enrichment.enabled:
        enrichment_worker = EnrichmentWorker(ctx)
        enrichment_worker.run()


# TODO: [Taskmaster] Simplify database backend creation
def _create_database_backend(
    site_root: Path,
    config: EgregoraConfig,
) -> tuple[str, Any]:
    """Create the main database backend for the pipeline.

    Returns a tuple of the resolved database URI and the Ibis backend connection.
    """
    db_uri = config.database.pipeline_db
    if not db_uri:
        msg = "Database setting 'database.pipeline_db' must be a non-empty connection URI."
        raise ValueError(msg)

    resolved_uri = resolve_db_uri(db_uri, site_root)
    return resolved_uri, ibis.connect(resolved_uri)


def _resolve_site_paths_or_raise(output_dir: Path, config: EgregoraConfig) -> MkDocsPaths:
    """Resolve site paths for the configured output format and validate structure."""
    site_paths = _resolve_pipeline_site_paths(output_dir, config)

    # Default validation for MkDocs/standard structure
    mkdocs_path = site_paths.mkdocs_path
    if not mkdocs_path or not mkdocs_path.exists():
        msg = (
            f"No mkdocs.yml found for site at {output_dir}. "
            "Run 'egregora init <site-dir>' before processing exports."
        )
        raise ValueError(msg)

    docs_dir = site_paths.docs_dir
    if not docs_dir.exists():
        msg = f"Docs directory not found: {docs_dir}. Re-run 'egregora init' to scaffold the MkDocs project."
        raise ValueError(msg)

    return site_paths


def _resolve_pipeline_site_paths(output_dir: Path, config: EgregoraConfig) -> MkDocsPaths:
    """Resolve site paths for the configured output format."""
    output_dir = output_dir.expanduser().resolve()
    return MkDocsPaths(output_dir, config=config)


def _create_gemini_client(model_name: str) -> genai.GenerativeModel:
    """Create a Gemini client with retry configuration."""
    # Safety settings to avoid blocking content.
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    return genai.GenerativeModel(model_name, safety_settings=safety_settings)


def _create_pipeline_context(run_params: PipelineRunParams) -> tuple[PipelineContext, Any]:
    """Create pipeline context with all resources and configuration.

    Returns a tuple of the PipelineContext and the pipeline_backend for cleanup.
    """
    resolved_output = run_params.output_dir.expanduser().resolve()

    refresh_tiers = {r.strip().lower() for r in (run_params.refresh or "").split(",") if r.strip()}
    site_paths = _resolve_site_paths_or_raise(resolved_output, run_params.config)
    _runtime_db_uri, pipeline_backend = _create_database_backend(site_paths.site_root, run_params.config)

    # Initialize database tables (CREATE TABLE IF NOT EXISTS)
    initialize_database(pipeline_backend)

    client_instance = run_params.client or _create_gemini_client(run_params.config.models.writer)
    cache_path = Path(run_params.config.paths.cache_dir)
    cache_dir = cache_path if cache_path.is_absolute() else site_paths.site_root / cache_path
    cache = PipelineCache(cache_dir, refresh_tiers=refresh_tiers)
    site_paths.egregora_dir.mkdir(parents=True, exist_ok=True)

    # Use the pipeline backend for storage to ensure we share the same connection
    # This prevents "read-only transaction" errors and database invalidation
    storage = DuckDBStorageManager.from_ibis_backend(pipeline_backend)
    annotations_store = AnnotationStore(storage)

    # Initialize TaskStore for async operations
    task_store = TaskStore(storage)

    _init_global_rate_limiter(run_params.config.quota)

    output_registry = create_default_output_registry()

    url_ctx = UrlContext(
        base_url="",
        site_prefix="",  # FIX: Empty prefix because MkDocsAdapter prepends media_dir
        base_path=site_paths.site_root,
    )

    config_obj = PipelineConfig(
        config=run_params.config,
        output_dir=resolved_output,
        site_root=site_paths.site_root,
        docs_dir=site_paths.docs_dir,
        posts_dir=site_paths.posts_dir,
        profiles_dir=site_paths.profiles_dir,
        media_dir=site_paths.media_dir,
        url_context=url_ctx,
    )

    state = PipelineState(
        run_id=run_params.run_id,
        start_time=run_params.start_time,
        source_type=run_params.source_type,
        input_path=run_params.input_path,
        client=client_instance,
        storage=storage,
        cache=cache,
        annotations_store=annotations_store,
        usage_tracker=UsageTracker(),
        output_registry=output_registry,
        smoke_test=run_params.smoke_test,
    )

    # Inject TaskStore into state/context
    state.task_store = task_store

    ctx = PipelineContext(config_obj, state)

    return ctx, pipeline_backend


@contextmanager
def _pipeline_environment(run_params: PipelineRunParams) -> Iterator[PipelineContext]:
    """Context manager that provisions and tears down pipeline resources."""
    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None
    ctx, pipeline_backend = _create_pipeline_context(run_params)

    if options is not None:
        options.default_backend = pipeline_backend

    try:
        yield ctx
    finally:
        try:
            ctx.cache.close()
        finally:
            if options is not None:
                options.default_backend = old_backend

            backend_close = getattr(pipeline_backend, "close", None)
            if callable(backend_close):
                backend_close()
            elif hasattr(pipeline_backend, "con") and hasattr(pipeline_backend.con, "close"):
                pipeline_backend.con.close()


def _parse_and_validate_source(
    adapter: Any,
    input_path: Path,
    timezone: str,
    *,
    output_adapter: OutputSink | None = None,
) -> ir.Table:
    """Parse source and return messages table.

    Args:
        adapter: Source adapter instance
        input_path: Path to input file
        timezone: Timezone string
        output_adapter: Optional output adapter (used by adapters that reprocess existing sites)

    Returns:
        messages_table: Parsed messages table

    """
    logger.info("[bold cyan]📦 Parsing with adapter:[/] %s", adapter.source_name)
    messages_table = adapter.parse(input_path, timezone=timezone, output_adapter=output_adapter)
    total_messages = messages_table.count().execute()
    logger.info("[green]✅ Parsed[/] %s messages", total_messages)

    metadata = adapter.get_metadata(input_path)
    logger.info("[yellow]👥 Group:[/] %s", metadata.get("group_name", "Unknown"))

    return messages_table


def _setup_content_directories(ctx: PipelineContext) -> None:
    """Create and validate content directories.

    Args:
        ctx: Pipeline context

    Raises:
        ValueError: If directories are not inside docs_dir

    """
    content_dirs = {
        "posts": ctx.posts_dir,
        "profiles": ctx.profiles_dir,
        "media": ctx.media_dir,
    }

    for label, directory in content_dirs.items():
        if label == "media":
            try:
                directory.relative_to(ctx.docs_dir)
            except ValueError:
                try:
                    directory.relative_to(ctx.site_root)
                except ValueError as exc:
                    msg = (
                        "Media directory must reside inside the MkDocs docs_dir or the site root. "
                        f"Expected parent {ctx.docs_dir} or {ctx.site_root}, got {directory}."
                    )
                    raise ValueError(msg) from exc
            directory.mkdir(parents=True, exist_ok=True)
            continue

        try:
            directory.relative_to(ctx.docs_dir)
        except ValueError as exc:
            msg = (
                f"{label.capitalize()} directory must reside inside the MkDocs docs_dir. "
                f"Expected parent {ctx.docs_dir}, got {directory}."
            )
            raise ValueError(msg) from exc
        directory.mkdir(parents=True, exist_ok=True)


def _process_commands_and_avatars(
    messages_table: ir.Table, ctx: PipelineContext, vision_model: str
) -> ir.Table:
    """Process egregora commands and avatar commands.

    Args:
        messages_table: Input messages table
        ctx: Pipeline context
        vision_model: Vision model identifier

    Returns:
        Messages table (unchanged, commands are side effects)

    """
    commands = extract_commands(messages_table)
    if commands:
        process_commands(commands, ctx.profiles_dir)
        logger.info("[magenta]🧾 Processed[/] %s /egregora commands", len(commands))
    else:
        logger.info("[magenta]🧾 No /egregora commands detected[/]")

    logger.info("[cyan]🖼️  Processing avatar commands...[/]")
    avatar_context = AvatarContext(
        docs_dir=ctx.docs_dir,
        media_dir=ctx.media_dir,
        profiles_dir=ctx.profiles_dir,
        vision_model=vision_model,
        cache=ctx.cache.enrichment,
    )
    avatar_results = process_avatar_commands(
        messages_table=messages_table,
        context=avatar_context,
    )
    if avatar_results:
        logger.info("[green]✓ Processed[/] %s avatar command(s)", len(avatar_results))

    return messages_table


def _prepare_pipeline_data(
    adapter: Any,
    run_params: PipelineRunParams,
    ctx: PipelineContext,
) -> PreparedPipelineData:
    """Prepare messages, filters, and windowing context for processing.

    Args:
        adapter: Input adapter instance
        run_params: Aggregated pipeline run parameters
        ctx: Pipeline context

    Returns:
        PreparedPipelineData with messages table, windows iterator, and updated context

    """
    config = run_params.config
    timezone = config.pipeline.timezone
    step_size = config.pipeline.step_size
    step_unit = config.pipeline.step_unit
    overlap_ratio = config.pipeline.overlap_ratio
    max_window_time_hours = config.pipeline.max_window_time
    max_window_time = timedelta(hours=max_window_time_hours) if max_window_time_hours else None
    enable_enrichment = config.enrichment.enabled

    from_date: date_type | None = None
    to_date: date_type | None = None
    if config.pipeline.from_date:
        from_date = date_type.fromisoformat(config.pipeline.from_date)
    if config.pipeline.to_date:
        to_date = date_type.fromisoformat(config.pipeline.to_date)

    vision_model = config.models.enricher_vision
    embedding_model = config.models.embedding

    output_sink = PipelineFactory.create_output_adapter(
        config,
        run_params.output_dir,
        site_root=ctx.site_root,
        registry=ctx.output_registry,
        url_context=ctx.url_context,
    )
    ctx = ctx.with_output_sink(output_sink)

    messages_table = _parse_and_validate_source(
        adapter, run_params.input_path, timezone, output_adapter=output_sink
    )
    _setup_content_directories(ctx)
    messages_table = _process_commands_and_avatars(messages_table, ctx, vision_model)

    filter_options = FilterOptions(
        from_date=from_date,
        to_date=to_date,
        checkpoint_enabled=config.pipeline.checkpoint_enabled,
    )
    messages_table = _apply_filters(
        messages_table,
        ctx,
        filter_options,
    )

    logger.info("🎯 [bold cyan]Creating windows:[/] step_size=%s, unit=%s", step_size, step_unit)
    window_config = WindowConfig(
        step_size=step_size,
        step_unit=step_unit,
        overlap_ratio=overlap_ratio,
        max_window_time=max_window_time,
    )
    windows_iterator = create_windows(
        messages_table,
        config=window_config,
    )

    # Update context with adapter
    ctx = ctx.with_adapter(adapter)

    # Index existing documents into RAG
    if ctx.config.rag.enabled:
        logger.info("[bold cyan]📚 Indexing existing documents into RAG...[/]")
        try:
            # Get existing documents from output format
            existing_docs = list(output_sink.documents())
            if existing_docs:
                index_documents(existing_docs)
                logger.info("[green]✓ Indexed %d existing documents into RAG[/]", len(existing_docs))
                reset_backend()
            else:
                logger.info("[dim]No existing documents to index[/]")
        except (ConnectionError, TimeoutError) as exc:
            logger.warning("[yellow]⚠️ RAG backend unavailable for indexing (non-critical): %s[/]", exc)
        except (ValueError, TypeError) as exc:
            logger.warning("[yellow]⚠️ Invalid document data for RAG indexing (non-critical): %s[/]", exc)
        except (OSError, PermissionError) as exc:
            logger.warning("[yellow]⚠️ Cannot access RAG storage for indexing (non-critical): %s[/]", exc)

    checkpoint_root = ctx.storage.checkpoint_dir or (ctx.output_dir / ".egregora" / "data")
    checkpoint_path = checkpoint_root / f"{ctx.run_id}-pipeline.json"

    return PreparedPipelineData(
        messages_table=messages_table,
        windows_iterator=windows_iterator,
        checkpoint_path=checkpoint_path,
        context=ctx,
        enable_enrichment=enable_enrichment,
        embedding_model=embedding_model,
    )


def _index_media_into_rag(
    *,
    enable_enrichment: bool,
    results: dict,
    ctx: PipelineContext,
    embedding_model: str,
) -> None:
    """Index media enrichments into RAG after window processing.

    Args:
        enable_enrichment: Whether enrichment is enabled
        results: Window processing results
        ctx: Pipeline context
        embedding_model: Embedding model identifier

    """
    if not (enable_enrichment and results):
        return

    # Media RAG indexing removed - will be reimplemented with egregora.rag
    # logger.info("[bold cyan]📚 Indexing media into RAG...[/]")
    # ... (removed for now)


# _save_checkpoint removed - replaced by Journal-based execution log


def _apply_date_filters(
    messages_table: ir.Table, from_date: date_type | None, to_date: date_type | None
) -> ir.Table:
    """Apply date range filtering."""
    if not (from_date or to_date):
        return messages_table

    original_count = messages_table.count().execute()
    if from_date and to_date:
        messages_table = messages_table.filter(
            (messages_table.ts.date() >= from_date) & (messages_table.ts.date() <= to_date)
        )
        logger.info("📅 [cyan]Filtering[/] from %s to %s", from_date, to_date)
    elif from_date:
        messages_table = messages_table.filter(messages_table.ts.date() >= from_date)
        logger.info("📅 [cyan]Filtering[/] from %s onwards", from_date)
    elif to_date:
        messages_table = messages_table.filter(messages_table.ts.date() <= to_date)
        logger.info("📅 [cyan]Filtering[/] up to %s", to_date)

    filtered_count = messages_table.count().execute()
    removed_by_date = original_count - filtered_count
    if removed_by_date > 0:
        logger.info("🗓️  [yellow]Filtered out[/] %s messages (kept %s)", removed_by_date, filtered_count)
    return messages_table


def _apply_checkpoint_filter(messages_table: ir.Table, *, checkpoint_enabled: bool) -> ir.Table:
    """Apply checkpoint-based resume logic.

    DEPRECATED: We now rely on window skipping in runner.py based on JOURNAL entries.
    However, for massive datasets, filtering at the source is still more efficient.

    TODO: [Refactor] Implement source-level filtering based on Max(window_end) from Journals.
    For now, we let runner.py skip windows individually.
    """
    # Just return full table - runner will skip processed windows
    return messages_table


@dataclass
class FilterOptions:
    """Options for filtering messages."""

    from_date: date_type | None = None
    to_date: date_type | None = None
    checkpoint_enabled: bool = False


def _apply_filters(
    messages_table: ir.Table,
    ctx: PipelineContext,
    options: FilterOptions,
) -> ir.Table:
    """Apply all filters: egregora messages, opted-out users, date range, checkpoint resume.

    Args:
        messages_table: Input messages table
        ctx: Pipeline context
        options: Filter configuration

    Returns:
        Filtered messages table

    """
    # Filter egregora messages
    messages_table, egregora_removed = filter_egregora_messages(messages_table)
    if egregora_removed:
        logger.info("[yellow]🧹 Removed[/] %s /egregora messages", egregora_removed)

    # Filter opted-out authors
    messages_table, removed_count = filter_opted_out_authors(messages_table, ctx.profiles_dir)
    if removed_count > 0:
        logger.warning("⚠️  %s messages removed from opted-out users", removed_count)

    # Date range filtering
    messages_table = _apply_date_filters(messages_table, options.from_date, options.to_date)

    # Checkpoint-based resume logic (Delegated to Runner / Journal check)
    return _apply_checkpoint_filter(messages_table, checkpoint_enabled=options.checkpoint_enabled)


def _init_global_rate_limiter(quota_config: Any) -> None:
    """Initialize the global rate limiter."""
    init_rate_limiter(
        requests_per_second=quota_config.per_second_limit,
        max_concurrency=quota_config.concurrency,
    )


def _generate_taxonomy(dataset: PreparedPipelineData) -> None:
    """Generate semantic taxonomy if enabled."""
    if dataset.context.config.rag.enabled:
        logger.info("[bold cyan]🏷️  Generating Semantic Taxonomy...[/]")
        try:
            tagged_count = generate_semantic_taxonomy(dataset.context.output_sink, dataset.context.config)
            if tagged_count > 0:
                logger.info("[green]✓ Applied semantic tags to %d posts[/]", tagged_count)
        except (ValueError, TypeError, AttributeError) as e:
            # Non-critical failure
            logger.warning("Auto-taxonomy failed: %s", e)


def run(run_params: PipelineRunParams) -> dict[str, dict[str, list[str]]]:
    """Run the complete write pipeline workflow.

    Args:
        run_params: Aggregated pipeline run parameters

    Returns:
        Dict mapping window labels to {'posts': [...], 'profiles': [...]}

    """
    logger.info("[bold cyan]🚀 Starting pipeline for source:[/] %s", run_params.source_type)

    # Create adapter with config for privacy settings
    # Instead of using singleton from registry, instantiate with config
    adapter_cls = ADAPTER_REGISTRY.get(run_params.source_type)
    if adapter_cls is None:
        msg = f"Unknown source type: {run_params.source_type}"
        raise ValueError(msg)

    # Instantiate adapter with config if it supports it (WhatsApp does)
    try:
        adapter = adapter_cls(config=run_params.config)
    except TypeError:
        # Fallback for adapters that don't accept config parameter
        adapter = adapter_cls()

    with _pipeline_environment(run_params) as ctx:
        try:
            dataset = _prepare_pipeline_data(adapter, run_params, ctx)

            results = {}
            max_processed_timestamp: datetime | None = None

            # New simplified loop: Iterator (ETL) -> Process (Execution)
            for conversation in get_pending_conversations(dataset):
                item_results = process_item(conversation)
                results.update(item_results)

                # Track max timestamp for checkpoint
                if max_processed_timestamp is None or conversation.window.end_time > max_processed_timestamp:
                    max_processed_timestamp = conversation.window.end_time

            _index_media_into_rag(
                enable_enrichment=dataset.enable_enrichment,
                results=results,
                ctx=dataset.context,
                embedding_model=dataset.embedding_model,
            )

            _generate_taxonomy(dataset)

            # Checkpoint saving removed - Journals are saved atomically during processing

            # Final pass for any lingering background tasks
            process_background_tasks(dataset.context)

            # Regenerate tags page with word cloud visualization
            if hasattr(dataset.context.output_sink, "regenerate_tags_page"):
                try:
                    logger.info("[bold cyan]🏷️  Regenerating tags page with word cloud...[/]")
                    dataset.context.output_sink.regenerate_tags_page()
                except (OSError, AttributeError, TypeError) as e:
                    logger.warning("Failed to regenerate tags page: %s", e)

            logger.info("[bold green]🎉 Pipeline completed successfully![/]")

        except KeyboardInterrupt:
            logger.warning("[yellow]⚠️  Pipeline cancelled by user (Ctrl+C)[/]")
            raise  # Re-raise to allow proper cleanup
        except Exception:
            # Broad catch is intentional: record failure for any exception, then re-raise
            raise  # Re-raise original exception to preserve error context

        return results
