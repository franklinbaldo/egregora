"""Write pipeline orchestration - executes the complete write workflow.

This module orchestrates the high-level flow for the 'write' command, coordinating:
- Input adapter selection and parsing
- Privacy and enrichment stages
- Window-based post generation
- Output adapter persistence
- Asynchronous task processing (banners, profiles)

Part of the three-layer architecture:
- orchestration/ (THIS) - Business workflows (WHAT to execute)
- pipeline/ - Generic infrastructure (HOW to execute)
- data_primitives/ - Core data models
"""

from __future__ import annotations

import contextlib
import logging
import math
import os
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import ibis
import ibis.common.exceptions
from google import genai

from egregora.agents.avatar import AvatarContext, process_avatar_commands
from egregora.agents.banner.worker import BannerWorker
from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker, schedule_enrichment
from egregora.agents.model_limits import PromptTooLargeError, get_model_context_limit
from egregora.agents.profile.worker import ProfileWorker
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.writer import WindowProcessingParams, write_posts_for_window
from egregora.config.settings import EgregoraConfig, load_egregora_config
from egregora.data_primitives.protocols import OutputSink, UrlContext
from egregora.database import initialize_database
from egregora.database.run_store import RunStore
from egregora.database.task_store import TaskStore
from egregora.input_adapters import ADAPTER_REGISTRY
from egregora.input_adapters.base import MediaMapping
from egregora.input_adapters.whatsapp.commands import extract_commands, filter_egregora_messages
from egregora.knowledge.profiles import filter_opted_out_authors, process_commands
from egregora.ops.media import process_media_for_window
from egregora.ops.taxonomy import generate_semantic_taxonomy
from egregora.orchestration.context import PipelineConfig, PipelineContext, PipelineRunParams, PipelineState
from egregora.orchestration.factory import PipelineFactory
from egregora.orchestration.strategies import process_with_auto_split
from egregora.output_adapters import create_default_output_registry
from egregora.output_adapters.mkdocs import derive_mkdocs_paths
from egregora.output_adapters.mkdocs.paths import compute_site_prefix
from egregora.transformations import (
    WindowConfig,
    create_windows,
    load_checkpoint,
    save_checkpoint,
)
from egregora.utils.cache import PipelineCache
from egregora.utils.metrics import UsageTracker
from egregora.utils.quota import QuotaTracker
from egregora.utils.rate_limit import init_rate_limiter

if TYPE_CHECKING:
    import ibis.expr.types as ir


logger = logging.getLogger(__name__)
__all__ = ["WhatsAppProcessOptions", "process_whatsapp_export", "run"]

MIN_WINDOWS_WARNING_THRESHOLD = 5


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


def _process_background_tasks(ctx: PipelineContext) -> None:
    """Process pending background tasks (banners, profiles, enrichment)."""
    if not hasattr(ctx, "task_store") or not ctx.task_store:
        return

    logger.info("⚙️  [bold cyan]Processing background tasks...[/]")

    # Run workers sequentially for now (can be parallelized later)
    # 1. Banner Generation (Highest priority - visual assets)
    banner_worker = BannerWorker(ctx)
    banners_processed = banner_worker.run()
    if banners_processed > 0:
        logger.info("Generated %d banners", banners_processed)

    # 2. Profile Updates (Coalescing optimization)
    profile_worker = ProfileWorker(ctx)
    profiles_processed = profile_worker.run()
    if profiles_processed > 0:
        logger.info("Updated %d profiles", profiles_processed)

    # 3. Enrichment (Lower priority - can catch up later)
    enrichment_worker = EnrichmentWorker(ctx)
    enrichment_processed = enrichment_worker.run()
    if enrichment_processed > 0:
        logger.info("Enriched %d items", enrichment_processed)


def _process_single_window(
    window: any, ctx: PipelineContext, depth: int = 0
) -> dict[str, dict[str, list[str]]]:
    """Process a single window with media extraction, enrichment, and post writing.

    Args:
        window: Window to process
        ctx: Pipeline context
        depth: Current split depth (for logging)

    Returns:
        Dict mapping window label to {'posts': [...], 'profiles': [...]}

    """
    indent = "  " * depth
    window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
    window_table = window.table
    window_count = window.size

    logger.info("%s➡️  [bold]%s[/] — %s messages (depth=%d)", indent, window_label, window_count, depth)

    # Process media
    output_sink = ctx.output_format
    if output_sink is None:
        msg = "Output adapter must be initialized before processing windows."
        raise RuntimeError(msg)

    url_context = ctx.url_context or UrlContext()
    window_table_processed, media_mapping = process_media_for_window(
        window_table=window_table,
        adapter=ctx.adapter,
        url_convention=output_sink.url_convention,
        url_context=url_context,
        zip_path=ctx.input_path,
    )

    # Media persistence is now deferred until after enrichment
    # to allow for proper slug generation and content processing.
    if media_mapping and not ctx.enable_enrichment:
        # Only persist immediately if enrichment is disabled (legacy/fallback mode)
        for media_doc in media_mapping.values():
            try:
                output_sink.persist(media_doc)
            except (OSError, PermissionError):
                logger.exception("Failed to write media file %s", media_doc.metadata.get("filename"))
            except ValueError:
                logger.exception("Invalid media document %s", media_doc.metadata.get("filename"))

    # Enrichment (Schedule tasks)
    if ctx.enable_enrichment:
        logger.info("%s✨ [cyan]Scheduling enrichment[/] for window %s", indent, window_label)
        enriched_table = _perform_enrichment(window_table_processed, media_mapping, ctx)
    else:
        enriched_table = window_table_processed

    # Write posts
    resources = PipelineFactory.create_writer_resources(ctx)
    adapter_summary, adapter_instructions = _extract_adapter_info(ctx)

    params = WindowProcessingParams(
        table=enriched_table,
        window_start=window.start_time,
        window_end=window.end_time,
        resources=resources,
        config=ctx.config,
        cache=ctx.cache,
        adapter_content_summary=adapter_summary,
        adapter_generation_instructions=adapter_instructions,
        run_id=str(ctx.run_id) if ctx.run_id else None,
    )
    result = write_posts_for_window(params)

    posts = result.get("posts", [])
    profiles = result.get("profiles", [])

    # Scheduled tasks are returned as "pending:<task_id>"
    scheduled_posts = sum(1 for p in posts if p.startswith("pending:"))
    generated_posts = len(posts) - scheduled_posts

    scheduled_profiles = sum(1 for p in profiles if p.startswith("pending:"))
    generated_profiles = len(profiles) - scheduled_profiles

    # Construct status message
    status_parts = []
    if generated_posts > 0:
        status_parts.append(f"{generated_posts} posts")
    if scheduled_posts > 0:
        status_parts.append(f"{scheduled_posts} scheduled posts")
    if generated_profiles > 0:
        status_parts.append(f"{generated_profiles} profiles")
    if scheduled_profiles > 0:
        status_parts.append(f"{scheduled_profiles} scheduled profiles")

    status_msg = ", ".join(status_parts) if status_parts else "0 items"

    logger.info(
        "%s[green]✔ Generated[/] %s for %s",
        indent,
        status_msg,
        window_label,
    )

    return {window_label: result}




# _ensure_run_events_table_exists and _record_run_event - REMOVED (2025-11-17)
# Per-window event tracking removed in favor of aggregated metrics in runs table
# See docs/SIMPLIFICATION_PLAN.md for details


def _resolve_context_token_limit(config: EgregoraConfig) -> int:
    """Resolve the effective context window token limit for the writer model.

    Args:
        config: Egregora configuration with model settings.

    Returns:
        Maximum number of prompt tokens available for a window.

    """
    use_full_window = getattr(config.pipeline, "use_full_context_window", False)

    if use_full_window:
        writer_model = config.models.writer
        limit = get_model_context_limit(writer_model)
        logger.debug(
            "Using full context window for writer model %s (limit=%d tokens)",
            writer_model,
            limit,
        )
        return limit

    limit = config.pipeline.max_prompt_tokens
    logger.debug("Using configured max_prompt_tokens cap: %d tokens", limit)
    return limit


def _calculate_max_window_size(config: EgregoraConfig) -> int:
    """Calculate maximum window size based on LLM context window.

    Uses rough heuristic: 5 tokens per message average.
    Leaves 20% buffer for prompt overhead (system prompt, tools, etc.).

    Args:
        config: Egregora configuration with model settings

    Returns:
        Maximum number of messages per window

    Example:
        >>> config.pipeline.max_prompt_tokens = 100_000
        >>> _calculate_max_window_size(config)
        16000  # (100k * 0.8) / 5

    """
    max_tokens = _resolve_context_token_limit(config)
    avg_tokens_per_message = 5  # Conservative estimate
    buffer_ratio = 0.8  # Leave 20% for system prompt, tools, etc.

    return int((max_tokens * buffer_ratio) / avg_tokens_per_message)


def _validate_window_size(window: any, max_size: int) -> None:
    """Validate window doesn't exceed LLM context limits.

    Args:
        window: Window object with size attribute
        max_size: Maximum allowed window size (messages)

    Raises:
        ValueError: If window exceeds max size

    """
    if window.size > max_size:
        msg = (
            f"Window {window.window_index} has {window.size} messages but max is {max_size}. "
            f"This limit is based on your model's context window. "
            f"Reduce --step-size to create smaller windows."
        )
        raise ValueError(msg)


def _process_all_windows(
    windows_iterator: any, ctx: PipelineContext
) -> tuple[dict[str, dict[str, list[str]]], datetime | None]:
    """Process all windows with tracking and error handling.

    Args:
        windows_iterator: Iterator of Window objects
        ctx: Pipeline context

    Returns:
        Tuple of (results dict, max_processed_timestamp)
        - results: Dict mapping window labels to {'posts': [...], 'profiles': [...]}
        - max_processed_timestamp: Latest end_time from successfully processed windows

    """
    results = {}
    max_processed_timestamp: datetime | None = None

    # Calculate max window size from LLM context (once)
    max_window_size = _calculate_max_window_size(ctx.config)
    effective_token_limit = _resolve_context_token_limit(ctx.config)
    logger.debug(
        "Max window size: %d messages (based on %d token context)",
        max_window_size,
        effective_token_limit,
    )

    # Get max_windows limit from config (default 1 for single-window behavior)
    max_windows = getattr(ctx.config.pipeline, "max_windows", 1)
    if max_windows == 0:
        max_windows = None  # 0 means process all windows

    windows_processed = 0
    for window in windows_iterator:
        # Check if we've hit the max_windows limit
        if max_windows is not None and windows_processed >= max_windows:
            logger.info("Reached max_windows limit (%d). Stopping processing.", max_windows)
            if max_windows < MIN_WINDOWS_WARNING_THRESHOLD:
                logger.warning(
                    "⚠️  Processing stopped early due to low 'max_windows' setting (%d). "
                    "This may result in incomplete data coverage. "
                    "Use --max-windows 0 or remove the limit to process all data.",
                    max_windows,
                )
            break
        # Skip empty windows
        if window.size == 0:
            logger.debug(
                "Skipping empty window %d (%s to %s)",
                window.window_index,
                window.start_time.strftime("%Y-%m-%d %H:%M"),
                window.end_time.strftime("%Y-%m-%d %H:%M"),
            )
            continue

        # Validate window size doesn't exceed LLM context limits
        _validate_window_size(window, max_window_size)

        # Process window
        window_results = process_with_auto_split(
            window, ctx, _process_single_window, depth=0, max_depth=5
        )
        results.update(window_results)

        # Track max processed timestamp for checkpoint
        if max_processed_timestamp is None or window.end_time > max_processed_timestamp:
            max_processed_timestamp = window.end_time

        # Process accumulated background tasks periodically or after each window?
        # Processing after each window keeps the queue small and provides incremental progress.
        _process_background_tasks(ctx)

        # Log summary (per-window event tracking removed - see SIMPLIFICATION_PLAN.md)
        posts_count = sum(len(r.get("posts", [])) for r in window_results.values())
        profiles_count = sum(len(r.get("profiles", [])) for r in window_results.values())
        logger.debug(
            "📊 Window %d: %s posts, %s profiles",
            window.window_index,
            posts_count,
            profiles_count,
        )

    return results, max_processed_timestamp


def _perform_enrichment(
    window_table: ir.Table,
    media_mapping: MediaMapping,
    ctx: PipelineContext,
) -> ir.Table:
    """Execute enrichment for a window's table.

    Phase 3: Extracted to eliminate duplication in resume/non-resume branches.

    Args:
        window_table: Table to enrich
        media_mapping: Media file mapping
        ctx: Pipeline context

    Returns:
        Enriched table

    """
    # Build PII prevention context for enricher from config
    pii_settings = ctx.config.privacy.pii_prevention.enricher
    pii_prevention = None
    if pii_settings.enabled:
        pii_prevention = {
            "enabled": True,
            "scope": pii_settings.scope.value,
            "custom_definition": pii_settings.custom_definition
            if pii_settings.scope.value == "custom"
            else None,
        }

    enrichment_context = EnrichmentRuntimeContext(
        cache=ctx.enrichment_cache,
        output_format=ctx.output_format,
        site_root=ctx.site_root,
        quota=ctx.quota_tracker,
        usage_tracker=ctx.usage_tracker,
        pii_prevention=pii_prevention,
        task_store=ctx.task_store,
    )

    # Schedule enrichment tasks
    schedule_enrichment(
        window_table,
        media_mapping,
        ctx.config.enrichment,
        enrichment_context,
        run_id=ctx.run_id,
    )

    # Execute enrichment immediately (synchronously) to ensure writer has access
    # to enriched media and updated references.
    worker = EnrichmentWorker(ctx)
    total_processed = 0
    while True:
        processed = worker.run()
        if processed == 0:
            break
        total_processed += processed
        logger.info("Synchronously processed %d enrichment tasks", processed)
    
    if total_processed > 0:
        logger.info("Enrichment complete. Processed %d items.", total_processed)

    # Return original table since enrichment happens in background
    return window_table


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


def _resolve_site_paths_or_raise(output_dir: Path, config: EgregoraConfig) -> dict[str, any]:
    """Resolve site paths for the configured output format and validate structure."""
    site_paths = _resolve_pipeline_site_paths(output_dir, config)

    # Default validation for MkDocs/standard structure
    mkdocs_path = site_paths.get("mkdocs_path")
    if not mkdocs_path or not mkdocs_path.exists():
        msg = (
            f"No mkdocs.yml found for site at {output_dir}. "
            "Run 'egregora init <site-dir>' before processing exports."
        )
        raise ValueError(msg)

    docs_dir = site_paths["docs_dir"]
    if not docs_dir.exists():
        msg = f"Docs directory not found: {docs_dir}. Re-run 'egregora init' to scaffold the MkDocs project."
        raise ValueError(msg)

    return site_paths


def _resolve_pipeline_site_paths(output_dir: Path, config: EgregoraConfig) -> dict[str, any]:
    """Resolve site paths for the configured output format."""
    output_dir = output_dir.expanduser().resolve()
    return derive_mkdocs_paths(output_dir, config=config)


def _create_gemini_client() -> genai.Client:
    """Create a Gemini client with retry configuration.

    The client reads the API key from GOOGLE_API_KEY environment variable automatically.
    """
    http_options = genai.types.HttpOptions(
        retryOptions=genai.types.HttpRetryOptions(
            attempts=15,
            initialDelay=2.0,
            maxDelay=60.0,
            expBase=2.0,
            httpStatusCodes=[429, 503],
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
        site_paths["site_root"], run_params.config
    )

    # Initialize database tables (CREATE TABLE IF NOT EXISTS)
    initialize_database(pipeline_backend)

    client_instance = run_params.client or _create_gemini_client()
    cache_dir = Path(".egregora-cache") / site_paths["site_root"].name
    cache = PipelineCache(cache_dir, refresh_tiers=refresh_tiers)
    site_paths["egregora_dir"].mkdir(parents=True, exist_ok=True)

    # Use the pipeline backend for storage to ensure we share the same connection
    # This prevents "read-only transaction" errors and database invalidation
    storage = PipelineFactory.create_storage_from_backend(pipeline_backend)
    annotations_store = AnnotationStore(storage)

    # Initialize TaskStore for async operations
    task_store = TaskStore(storage)

    quota_tracker = QuotaTracker(site_paths["egregora_dir"], run_params.config.quota.daily_llm_requests)

    _init_global_rate_limiter(run_params.config.quota)

    output_registry = create_default_output_registry()

    url_ctx = UrlContext(
        base_url="",
        site_prefix=compute_site_prefix(site_paths["site_root"], site_paths["docs_dir"]),
        base_path=site_paths["site_root"],
    )

    config_obj = PipelineConfig(
        config=run_params.config,
        output_dir=resolved_output,
        site_root=site_paths["site_root"],
        docs_dir=site_paths["docs_dir"],
        posts_dir=site_paths["posts_dir"],
        profiles_dir=site_paths["profiles_dir"],
        media_dir=site_paths["media_dir"],
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
        quota_tracker=quota_tracker,
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
                try:
                    if ctx.client:
                        ctx.client.close()
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
    if ctx.config.rag.enabled and ctx.rag_backend:
        logger.info("[bold cyan]📚 Indexing existing documents into RAG...[/]")
        try:
            # Get existing documents from output format
            existing_docs = list(output_format.documents())
            if existing_docs:
                ctx.rag_backend.index_documents(existing_docs)
                logger.info("[green]✓ Indexed %d existing documents into RAG[/]", len(existing_docs))
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
            tagged_count = generate_semantic_taxonomy(
                dataset.context.output_format,
                dataset.context.config,
                dataset.context.rag_backend,
            )
            if tagged_count > 0:
                logger.info("[green]✓ Applied semantic tags to %d posts[/]", tagged_count)
        except Exception as e:  # noqa: BLE001
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
            temp_storage = PipelineFactory.create_storage_from_connection(runs_conn)
            run_store = RunStore(temp_storage)
        else:
            logger.warning("Unable to access DuckDB connection for run tracking - runs will not be recorded")

        # Record run start
        _record_run_start(run_store, run_id, started_at)

        try:
            dataset = _prepare_pipeline_data(adapter, run_params, ctx)
            results, max_processed_timestamp = _process_all_windows(dataset.windows_iterator, dataset.context)
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
            # (In case there are stragglers)
            _process_background_tasks(dataset.context)

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
