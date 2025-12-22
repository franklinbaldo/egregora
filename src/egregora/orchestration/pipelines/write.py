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

import contextlib
import json
import logging
import math
import os
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import ibis
import ibis.common.exceptions
from google import genai
from rich.console import Console
from rich.panel import Panel

from egregora.agents.avatar import AvatarContext, process_avatar_commands
from egregora.agents.banner.worker import BannerWorker
from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker, schedule_enrichment
from egregora.agents.profile.worker import ProfileWorker
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.types import PromptTooLargeError
from egregora.agents.writer import WindowProcessingParams, write_posts_for_window
from egregora.config import RuntimeContext, load_egregora_config
from egregora.config.settings import EgregoraConfig, parse_date_arg, validate_timezone
from egregora.constants import SourceType, WindowUnit
from egregora.data_primitives.protocols import OutputSink, UrlContext
from egregora.database import initialize_database
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.run_store import RunStore
from egregora.database.task_store import TaskStore
from egregora.init import ensure_mkdocs_project
from egregora.input_adapters import ADAPTER_REGISTRY
from egregora.input_adapters.whatsapp.commands import extract_commands, filter_egregora_messages
from egregora.knowledge.profiles import filter_opted_out_authors, process_commands
from egregora.ops.media import process_media_for_window
from egregora.ops.taxonomy import generate_semantic_taxonomy
from egregora.orchestration.context import PipelineConfig, PipelineContext, PipelineRunParams, PipelineState
from egregora.orchestration.factory import PipelineFactory
from egregora.orchestration.runner import PipelineRunner
from egregora.output_adapters import create_default_output_registry
from egregora.output_adapters.mkdocs import MkDocsPaths
from egregora.rag import index_documents, reset_backend
from egregora.transformations import (
    WindowConfig,
    create_windows,
    load_checkpoint,
    save_checkpoint,
)
from egregora.utils.cache import PipelineCache
from egregora.utils.env import get_google_api_keys, validate_gemini_api_key
from egregora.utils.metrics import UsageTracker
from egregora.utils.rate_limit import init_rate_limiter

try:
    import dotenv
except ImportError:
    dotenv = None

if TYPE_CHECKING:
    import uuid

    import ibis.expr.types as ir

    from egregora.input_adapters.base import MediaMapping


logger = logging.getLogger(__name__)
console = Console()
__all__ = ["WhatsAppProcessOptions", "WriteCommandOptions", "process_whatsapp_export", "run", "run_cli_flow"]

MIN_WINDOWS_WARNING_THRESHOLD = 5


def run_async_safely(coro: Any) -> Any:
    """Run an async coroutine safely, handling nested event loops.

    If an event loop is already running (e.g., in Jupyter or nested calls),
    this will use run_until_complete instead of asyncio.run().
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - use asyncio.run()
        return asyncio.run(coro)
    else:
        # Loop is already running - use run_until_complete in a new thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()


@dataclass
class WriteCommandOptions:
    """Options for the write command."""

    input_file: Path
    source: SourceType
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
    economic_mode: bool
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
    # Note: retrieval_mode, retrieval_nprobe, retrieval_overfetch removed (legacy DuckDB VSS settings)
    max_prompt_tokens: int = 100_000
    use_full_context_window: bool = False
    client: genai.Client | None = None
    refresh: str | None = None


def _load_dotenv_if_available(output_dir: Path) -> None:
    if dotenv:
        dotenv.load_dotenv(output_dir / ".env")
        dotenv.load_dotenv()  # Check CWD as well


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
        os.environ["GOOGLE_API_KEY"] = api_keys[0]
        return

    console.print("[cyan]Validating Gemini API key...[/cyan]")
    validation_errors: list[str] = []
    for key in api_keys:
        try:
            validate_gemini_api_key(key)
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
                if k == "source" and isinstance(v, str):
                    defaults[k] = SourceType(v)
                elif k == "step_unit" and isinstance(v, str):
                    defaults[k] = WindowUnit(v)
                elif k == "output" and isinstance(v, str):
                    defaults[k] = Path(v)
                else:
                    defaults[k] = v
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing options JSON: {e}[/red]")
            raise SystemExit(1) from e

    return WriteCommandOptions(input_file=input_file, **defaults)


def run_cli_flow(
    input_file: Path,
    *,
    output: Path = Path("site"),
    source: SourceType = SourceType.WHATSAPP,
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
    economic_mode: bool = False,
    refresh: str | None = None,
    force: bool = False,
    debug: bool = False,
    options: str | None = None,
) -> None:
    """Execute the write flow from CLI arguments."""
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
        "economic_mode": economic_mode,
        "refresh": refresh,
        "force": force,
        "debug": debug,
    }

    parsed_options = _resolve_write_options(
        input_file=input_file,
        options_json=options,
        cli_defaults=cli_values,
    )

    if parsed_options.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    from_date_obj, to_date_obj = None, None
    if parsed_options.from_date:
        try:
            from_date_obj = parse_date_arg(parsed_options.from_date, "from_date")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1) from e
    if parsed_options.to_date:
        try:
            to_date_obj = parse_date_arg(parsed_options.to_date, "to_date")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1) from e

    if parsed_options.timezone:
        try:
            validate_timezone(parsed_options.timezone)
            console.print(f"[green]Using timezone: {parsed_options.timezone}[/green]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1) from e

    output_dir = parsed_options.output.expanduser().resolve()

    # Ensure MkDocs project exists (imported logic)
    # Reimplementing simplified version of _ensure_mkdocs_scaffold to avoid circular imports if it was in CLI
    # But we can import it if it is in init.
    # The original cli code had interactive prompts. Since we moved logic here, we should keep it
    # or rely on init being run.
    # For now, let's assume non-interactive or minimal check, or duplicate the check.
    # However, to be cleaner, we can just check if it exists and warn.
    # The original CLI `_ensure_mkdocs_scaffold` handled prompting.
    # Let's import `ensure_mkdocs_project` and do a basic check.

    config_path = output_dir / ".egregora.toml"

    if not config_path.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Initializing site in %s", output_dir)
        ensure_mkdocs_project(output_dir)

    _validate_api_key(output_dir)

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
                f"[cyan]Source:[/cyan] {parsed_options.source.value}\n[cyan]Input:[/cyan] {parsed_options.input_file}\n[cyan]Output:[/cyan] {output_dir}\n[cyan]Windowing:[/cyan] {parsed_options.step_size} {parsed_options.step_unit.value}",
                title="⚙️  Egregora Pipeline",
                border_style="cyan",
            )
        )
        run_params = PipelineRunParams(
            output_dir=runtime.output_dir,
            config=egregora_config,
            source_type=parsed_options.source.value,
            input_path=runtime.input_file,
            refresh="all" if parsed_options.force else parsed_options.refresh,
        )
        run(run_params)
        console.print("[green]Processing completed successfully.[/green]")
    except Exception as e:
        console.print_exception(show_locals=False)
        console.print(f"[red]Pipeline failed: {e}[/]")
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
            # Note: retrieval_mode, retrieval_nprobe, retrieval_overfetch were legacy DuckDB VSS settings
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
    windows_iterator: any
    checkpoint_path: Path
    context: PipelineContext
    enable_enrichment: bool
    embedding_model: str


# _create_writer_resources REMOVED - functionality moved to PipelineFactory.create_writer_resources


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


# _process_background_tasks REMOVED - functionality moved to PipelineRunner

# _process_single_window REMOVED - functionality moved to PipelineRunner

# _process_window_with_auto_split REMOVED - functionality moved to PipelineRunner

# _warn_if_window_too_small REMOVED - functionality moved to PipelineRunner

# _ensure_split_depth REMOVED - functionality moved to PipelineRunner

# _split_window_for_retry REMOVED - functionality moved to PipelineRunner

# _resolve_context_token_limit REMOVED - functionality moved to PipelineRunner

# _calculate_max_window_size REMOVED - functionality moved to PipelineRunner

# _validate_window_size REMOVED - functionality moved to PipelineRunner

# _process_all_windows REMOVED - functionality moved to PipelineRunner

# _perform_enrichment REMOVED - functionality moved to PipelineRunner


def _create_database_backends(
    site_root: Path,
    config: EgregoraConfig,
) -> tuple[str, any, any]:
    """Create database backends for pipeline and runs tracking.

    Uses Ibis for database abstraction, allowing future migration to
    other databases (Postgres, SQLite, etc.) via connection strings.

    Args:
        site_root: Root directory for the site
        config: Egregora configuration

    Returns:
        Tuple of (runtime_db_uri, pipeline_backend, runs_backend).

    Notes:
        DuckDB file URIs with the pattern ``duckdb:///./relative/path.duckdb`` are
        resolved relative to ``site_root`` to keep configuration portable while
        still using proper connection strings.

    """

    def _validate_and_connect(value: str, setting_name: str) -> tuple[str, any]:
        if not value:
            msg = f"Database setting '{setting_name}' must be a non-empty connection URI."
            raise ValueError(msg)

        parsed = urlparse(value)
        if not parsed.scheme:
            msg = (
                "Database setting '{setting}' must be provided as an Ibis-compatible connection "
                "URI (e.g. 'duckdb:///absolute/path/to/file.duckdb' or 'postgres://user:pass@host/db')."
            )
            raise ValueError(msg.format(setting=setting_name))

        if len(parsed.scheme) == 1 and value[1:3] in {":/", ":\\"}:
            msg = (
                "Database setting '{setting}' looks like a filesystem path. Provide a full connection "
                "URI instead (see the database settings documentation)."
            )
            raise ValueError(msg.format(setting=setting_name))

        normalized_value = value

        if parsed.scheme == "duckdb" and not parsed.netloc:
            path_value = parsed.path
            if path_value and path_value not in {"/:memory:", ":memory:", "memory", "memory:"}:
                if path_value.startswith("/./"):
                    fs_path = (site_root / Path(path_value[3:])).resolve()
                else:
                    fs_path = Path(path_value).resolve()
                fs_path.parent.mkdir(parents=True, exist_ok=True)
                normalized_value = f"duckdb://{fs_path}"

        return normalized_value, ibis.connect(normalized_value)

    runtime_db_uri, pipeline_backend = _validate_and_connect(
        config.database.pipeline_db, "database.pipeline_db"
    )
    _runs_db_uri, runs_backend = _validate_and_connect(config.database.runs_db, "database.runs_db")

    return runtime_db_uri, pipeline_backend, runs_backend


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


def _create_gemini_client() -> genai.Client:
    """Create a Gemini client with retry configuration.

    The client reads the API key from GOOGLE_API_KEY environment variable automatically.

    We disable retries for 429 (Resource Exhausted) to allow our application-level
    Model/Key rotator to handle it immediately (Story 8).
    We still retry 503 (Service Unavailable).
    """
    http_options = genai.types.HttpOptions(
        retryOptions=genai.types.HttpRetryOptions(
            attempts=3,  # Reduced from 15
            initialDelay=1.0,
            maxDelay=10.0,
            expBase=2.0,
            httpStatusCodes=[503],  # Only retry 503 at client level. 429 handled by app.
        )
    )
    return genai.Client(http_options=http_options)


def _create_pipeline_context(run_params: PipelineRunParams) -> tuple[PipelineContext, any, any]:
    """Create pipeline context with all resources and configuration.

    Args:
        run_params: Aggregated pipeline run parameters

    Returns:
        Tuple of (PipelineContext, pipeline_backend, runs_backend)
        The backends are returned for cleanup by the context manager.

    """
    resolved_output = run_params.output_dir.expanduser().resolve()

    refresh_tiers = {r.strip().lower() for r in (run_params.refresh or "").split(",") if r.strip()}
    site_paths = _resolve_site_paths_or_raise(resolved_output, run_params.config)
    _runtime_db_uri, pipeline_backend, runs_backend = _create_database_backends(
        site_paths.site_root, run_params.config
    )

    # Initialize database tables (CREATE TABLE IF NOT EXISTS)
    initialize_database(pipeline_backend)

    client_instance = run_params.client or _create_gemini_client()
    cache_path = Path(run_params.config.paths.cache_dir)
    if cache_path.is_absolute():
        cache_dir = cache_path
    else:
        cache_dir = site_paths.site_root / cache_path
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
    )

    # Inject TaskStore into state/context
    state.task_store = task_store

    ctx = PipelineContext(config_obj, state)

    return ctx, pipeline_backend, runs_backend


@contextmanager
def _pipeline_environment(run_params: PipelineRunParams) -> any:
    """Context manager that provisions and tears down pipeline resources.

    Args:
        run_params: Aggregated pipeline run parameters

    Yields:
        Tuple of (PipelineContext, runs_backend) for use in the pipeline

    """
    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None
    ctx, pipeline_backend, runs_backend = _create_pipeline_context(run_params)

    if options is not None:
        options.default_backend = pipeline_backend


    try:
        yield ctx, runs_backend
    finally:
        try:
            ctx.cache.close()
        finally:
            try:
                close_method = getattr(runs_backend, "close", None)
                if callable(close_method):
                    close_method()
                elif hasattr(runs_backend, "con") and hasattr(runs_backend.con, "close"):
                    runs_backend.con.close()
            finally:
                if options is not None:
                    options.default_backend = old_backend
                backend_close = getattr(pipeline_backend, "close", None)
                if callable(backend_close):
                    backend_close()
                elif hasattr(pipeline_backend, "con") and hasattr(pipeline_backend.con, "close"):
                    pipeline_backend.con.close()

def _parse_and_validate_source(
    adapter: any,
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
        cache=ctx.enrichment_cache,
    )
    avatar_results = process_avatar_commands(
        messages_table=messages_table,
        context=avatar_context,
    )
    if avatar_results:
        logger.info("[green]✓ Processed[/] %s avatar command(s)", len(avatar_results))

    return messages_table


def _prepare_pipeline_data(
    adapter: any,
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

    output_format = PipelineFactory.create_output_adapter(
        config,
        run_params.output_dir,
        site_root=ctx.site_root,
        registry=ctx.output_registry,
        url_context=ctx.url_context,
    )
    ctx = ctx.with_output_format(output_format)

    messages_table = _parse_and_validate_source(
        adapter, run_params.input_path, timezone, output_adapter=output_format
    )
    _setup_content_directories(ctx)
    messages_table = _process_commands_and_avatars(messages_table, ctx, vision_model)

    checkpoint_path = ctx.site_root / ".egregora" / "checkpoint.json"
    filter_options = FilterOptions(
        from_date=from_date,
        to_date=to_date,
        checkpoint_enabled=config.pipeline.checkpoint_enabled,
    )
    messages_table = _apply_filters(
        messages_table,
        ctx,
        filter_options,
        checkpoint_path,
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
            existing_docs = list(output_format.documents())
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


def _save_checkpoint(results: dict, max_processed_timestamp: datetime | None, checkpoint_path: Path) -> None:
    """Save checkpoint after successful window processing.

    Args:
        results: Window processing results
        max_processed_timestamp: Latest end_time from successfully processed windows
        checkpoint_path: Path to checkpoint file

    """
    if not results or max_processed_timestamp is None:
        logger.warning(
            "⚠️  [yellow]No windows processed[/] - checkpoint not saved. "
            "All windows may have been empty or filtered out."
        )
        return

    # Count total messages processed (approximate from results)
    total_posts = sum(len(r.get("posts", [])) for r in results.values())

    save_checkpoint(checkpoint_path, max_processed_timestamp, total_posts)
    logger.info(
        "💾 [cyan]Checkpoint saved:[/] processed up to %s (%d posts written)",
        max_processed_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        total_posts,
    )


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


def _apply_checkpoint_filter(
    messages_table: ir.Table, checkpoint_path: Path, *, checkpoint_enabled: bool
) -> ir.Table:
    """Apply checkpoint-based resume logic."""
    if not checkpoint_enabled:
        logger.info("🆕 [cyan]Full rebuild[/] (checkpoint disabled - default behavior)")
        return messages_table

    checkpoint = load_checkpoint(checkpoint_path)
    if not (checkpoint and "last_processed_timestamp" in checkpoint):
        logger.info("🆕 [cyan]Starting fresh[/] (checkpoint enabled, but no checkpoint found)")
        return messages_table

    last_timestamp_str = checkpoint["last_processed_timestamp"]
    last_timestamp = datetime.fromisoformat(last_timestamp_str)

    # Ensure timezone-aware comparison
    utc_zone = ZoneInfo("UTC")
    if last_timestamp.tzinfo is None:
        last_timestamp = last_timestamp.replace(tzinfo=utc_zone)
    else:
        last_timestamp = last_timestamp.astimezone(utc_zone)

    original_count = messages_table.count().execute()
    messages_table = messages_table.filter(messages_table.ts > last_timestamp)
    filtered_count = messages_table.count().execute()
    resumed_count = original_count - filtered_count

    if resumed_count > 0:
        logger.info(
            "♻️  [cyan]Resuming:[/] skipped %s already processed messages (last: %s)",
            resumed_count,
            last_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        )
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
    checkpoint_path: Path,
) -> ir.Table:
    """Apply all filters: egregora messages, opted-out users, date range, checkpoint resume.

    Args:
        messages_table: Input messages table
        ctx: Pipeline context
        options: Filter configuration
        checkpoint_path: Path to checkpoint file

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

    # Checkpoint-based resume logic
    return _apply_checkpoint_filter(
        messages_table, checkpoint_path, checkpoint_enabled=options.checkpoint_enabled
    )


def _init_global_rate_limiter(quota_config: any) -> None:
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
            tagged_count = generate_semantic_taxonomy(dataset.context.output_format, dataset.context.config)
            if tagged_count > 0:
                logger.info("[green]✓ Applied semantic tags to %d posts[/]", tagged_count)
        except Exception as e:
            # Non-critical failure
            logger.warning("Auto-taxonomy failed: %s", e)


def _record_run_start(run_store: RunStore | None, run_id: uuid.UUID, started_at: datetime) -> None:
    """Record the start of a pipeline run in the database.

    Args:
        run_store: Run store for tracking (None to skip tracking)
        run_id: Unique identifier for this run
        started_at: Timestamp when run started

    """
    if run_store is None:
        return

    try:
        run_store.mark_run_started(
            run_id=run_id,
            stage="write",
            started_at=started_at,
        )
    except (OSError, PermissionError) as exc:
        logger.debug("Failed to record run start (database unavailable): %s", exc)
    except ValueError as exc:
        logger.debug("Failed to record run start (invalid data): %s", exc)


def _record_run_completion(
    run_store: RunStore | None,
    run_id: uuid.UUID,
    started_at: datetime,
    results: dict[str, dict[str, list[str]]],
) -> None:
    """Record successful completion of a pipeline run.

    Args:
        run_store: Run store for tracking (None to skip tracking)
        run_id: Unique identifier for this run
        started_at: Timestamp when run started
        results: Results dict mapping window labels to posts/profiles

    """
    if run_store is None:
        return

    try:
        finished_at = datetime.now(UTC)
        duration_seconds = (finished_at - started_at).total_seconds()

        total_posts = sum(len(r.get("posts", [])) for r in results.values())
        total_profiles = sum(len(r.get("profiles", [])) for r in results.values())
        num_windows = len(results)

        run_store.mark_run_completed(
            run_id=run_id,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            rows_out=total_posts + total_profiles,
        )
        logger.debug(
            "Recorded pipeline run: %s (posts=%d, profiles=%d, windows=%d)",
            run_id,
            total_posts,
            total_profiles,
            num_windows,
        )
    except (OSError, PermissionError) as exc:
        logger.debug("Failed to record run completion (database unavailable): %s", exc)
    except ValueError as exc:
        logger.debug("Failed to record run completion (invalid data): %s", exc)


def _record_run_failure(
    run_store: RunStore | None, run_id: uuid.UUID, started_at: datetime, exc: Exception
) -> None:
    """Record failure of a pipeline run.

    Args:
        run_store: Run store for tracking (None to skip tracking)
        run_id: Unique identifier for this run
        started_at: Timestamp when run started
        exc: Exception that caused the failure

    """
    if run_store is None:
        return

    try:
        finished_at = datetime.now(UTC)
        duration_seconds = (finished_at - started_at).total_seconds()
        error_msg = f"{type(exc).__name__}: {exc!s}"

        run_store.mark_run_failed(
            run_id=run_id,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            error=error_msg[:500],
        )
    except (OSError, PermissionError) as tracking_exc:
        logger.debug("Failed to record run failure (database unavailable): %s", tracking_exc)
    except ValueError as tracking_exc:
        logger.debug("Failed to record run failure (invalid data): %s", tracking_exc)


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

    # Generate run ID and timestamp for tracking
    run_id = run_params.run_id
    started_at = run_params.start_time

    with _pipeline_environment(run_params) as (ctx, runs_backend):
        # Create RunStore from backend for abstracted run tracking
        runs_conn = getattr(runs_backend, "con", None)
        run_store = None
        if runs_conn is not None:
            # Properly wrap the connection to ensure ibis_conn is synchronized
            temp_storage = DuckDBStorageManager.from_connection(runs_conn)
            run_store = RunStore(temp_storage)
        else:
            logger.warning("Unable to access DuckDB connection for run tracking - runs will not be recorded")

        # Record run start
        _record_run_start(run_store, run_id, started_at)

        try:
            dataset = _prepare_pipeline_data(adapter, run_params, ctx)

            # Use PipelineRunner for execution
            runner = PipelineRunner(dataset.context)
            results, max_processed_timestamp = runner.process_windows(dataset.windows_iterator)

            _index_media_into_rag(
                enable_enrichment=dataset.enable_enrichment,
                results=results,
                ctx=dataset.context,
                embedding_model=dataset.embedding_model,
            )

            _generate_taxonomy(dataset)

            # Save checkpoint first (critical path)
            _save_checkpoint(results, max_processed_timestamp, dataset.checkpoint_path)

            # Process remaining background tasks after all windows are done
            runner.process_background_tasks()

            # Regenerate tags page with word cloud visualization
            if hasattr(dataset.context.output_format, "regenerate_tags_page"):
                try:
                    logger.info("[bold cyan]🏷️  Regenerating tags page with word cloud...[/]")
                    dataset.context.output_format.regenerate_tags_page()
                except (OSError, AttributeError, TypeError) as e:
                    logger.warning("Failed to regenerate tags page: %s", e)

            # Update run to completed
            _record_run_completion(run_store, run_id, started_at, results)

            logger.info("[bold green]🎉 Pipeline completed successfully![/]")

        except KeyboardInterrupt:
            logger.warning("[yellow]⚠️  Pipeline cancelled by user (Ctrl+C)[/]")
            # Mark run as cancelled (using failed status with specific error message)
            if run_store:
                with contextlib.suppress(Exception):
                    run_store.mark_run_failed(
                        run_id=run_id,
                        finished_at=datetime.now(UTC),
                        duration_seconds=(datetime.now(UTC) - started_at).total_seconds(),
                        error="Cancelled by user (KeyboardInterrupt)",
                    )
            raise  # Re-raise to allow proper cleanup
        except Exception as exc:
            # Broad catch is intentional: record failure for any exception, then re-raise
            _record_run_failure(run_store, run_id, started_at, exc)
            raise  # Re-raise original exception to preserve error context

        return results