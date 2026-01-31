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
import os
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from google import genai
from rich.console import Console
from rich.panel import Panel

from egregora.agents.banner.worker import BannerWorker
from egregora.agents.commands import command_to_announcement, filter_commands
from egregora.agents.commands import extract_commands as extract_commands_list
from egregora.agents.enricher import EnrichmentWorker
from egregora.agents.profile.generator import generate_profile_posts
from egregora.agents.profile.worker import ProfileWorker
from egregora.agents.types import Message, WriterResources
from egregora.agents.writer import WindowProcessingParams, write_posts_for_window
from egregora.config import RuntimeContext, load_egregora_config
from egregora.config.settings import EgregoraConfig
from egregora.constants import WindowUnit
from egregora.data_primitives.document import Document
from egregora.input_adapters import ADAPTER_REGISTRY
from egregora.input_adapters.exceptions import UnknownAdapterError
from egregora.llm.exceptions import AllModelsExhaustedError
from egregora.ops.taxonomy import generate_semantic_taxonomy
from egregora.orchestration.context import PipelineContext, PipelineRunParams
from egregora.orchestration.exceptions import (
    CommandAnnouncementError,
    OutputSinkError,
    ProfileGenerationError,
)
from egregora.orchestration.pipelines.etl.preparation import (
    Conversation,
    PreparedPipelineData,
    get_pending_conversations,
    prepare_pipeline_data,
    validate_dates,
    validate_timezone_arg,
)
from egregora.orchestration.pipelines.etl.setup import (
    ensure_site_initialized,
    pipeline_environment,
    validate_api_key,
)

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
    client: genai.Client | None = None
    refresh: str | None = None


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
    exit_on_error: bool = True,
) -> None:
    """Execute the write flow from CLI arguments.

    Args:
        source: Can be a source type (e.g., "whatsapp"), a source key from config, or None.
                If None, will use default_source from config, or run all sources if default is None.
        exit_on_error: If True, raise SystemExit(1) on failure. If False, re-raise the exception.

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

    from_date_obj, to_date_obj = validate_dates(from_date, to_date)
    validate_timezone_arg(timezone)

    output_dir = output.expanduser().resolve()
    ensure_site_initialized(output_dir)
    try:
        validate_api_key(output_dir)
    except SystemExit as e:
        if exit_on_error:
            raise
        # Wrap SystemExit in RuntimeError so callers (like demo) can handle it gracefully
        msg = f"API key validation failed: {e}"
        raise RuntimeError(msg) from e

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
        except (AllModelsExhaustedError, RuntimeError) as e:
            # Re-raise this specific error so the 'demo' command can catch it
            raise e
        except Exception as e:
            console.print_exception(show_locals=False)
            console.print(f"[red]Pipeline failed for source '{source_key}': {e}[/]")
            if exit_on_error:
                raise SystemExit(1) from e
            raise e


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
                msg = f"Failed to generate announcement: {exc}"
                raise CommandAnnouncementError(msg) from exc

    clean_messages_list = filter_commands(messages_list)

    # Convert to DTOs
    messages_dtos: list[Message] = []
    for msg_dict in clean_messages_list:
        try:
            # Basic conversion - assuming keys match
            if "event_id" in msg_dict and "ts" in msg_dict and "author_uuid" in msg_dict:
                # Filter only valid keys
                valid_keys = Message.model_fields.keys()
                filtered_dict = {k: v for k, v in msg_dict.items() if k in valid_keys}
                messages_dtos.append(Message(**filtered_dict))
        except (ValueError, TypeError):
            continue

    # Prepare Resources
    resources = WriterResources.from_pipeline_context(ctx)

    params = WindowProcessingParams(
        table=conversation.messages_table,
        messages=messages_dtos,
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
                msg = f"Failed to persist post {post.document_id}: {exc}"
                raise OutputSinkError(msg) from exc

    # EXECUTE PROFILE GENERATOR
    window_date = conversation.window.start_time.strftime("%Y-%m-%d")
    try:
        profile_docs = cast(
            "list[Document]",
            generate_profile_posts(ctx=ctx, messages=clean_messages_list, window_date=window_date),
        )
        for profile_doc in profile_docs:
            try:
                output_sink.persist(profile_doc)
                profiles.append(profile_doc.document_id)
            except Exception as exc:
                msg = f"Failed to persist profile {profile_doc.document_id}: {exc}"
                raise OutputSinkError(msg) from exc
    except Exception as exc:
        if isinstance(exc, OutputSinkError):
            raise
        msg = f"Failed to generate profile posts: {exc}"
        raise ProfileGenerationError(msg) from exc

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
        raise UnknownAdapterError(run_params.source_type)

    # Instantiate adapter with config if it supports it (WhatsApp does)
    try:
        adapter = adapter_cls(config=run_params.config)
    except TypeError:
        # Fallback for adapters that don't accept config parameter
        adapter = adapter_cls()

    with pipeline_environment(run_params) as ctx:
        try:
            dataset = prepare_pipeline_data(adapter, run_params, ctx)

            results = {}
            max_processed_timestamp: datetime | None = None

            # New simplified loop: Iterator (ETL) -> Process (Execution)
            for conversation in get_pending_conversations(dataset):
                item_results = process_item(conversation)
                results.update(item_results)

                # Track max timestamp for checkpoint
                if max_processed_timestamp is None or conversation.window.end_time > max_processed_timestamp:
                    max_processed_timestamp = conversation.window.end_time

            _generate_taxonomy(dataset)

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

        return results
