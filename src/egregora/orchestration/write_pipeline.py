"""Write pipeline orchestration - executes the complete write workflow.

This module orchestrates the high-level flow for the 'write' command, coordinating:
- Input adapter selection and parsing
- Privacy and enrichment stages
- Window-based post generation
- Output adapter persistence

Part of the three-layer architecture:
- orchestration/ (THIS) - Business workflows (WHAT to execute)
- pipeline/ - Generic infrastructure (HOW to execute)
- data_primitives/ - Core data models
"""

from __future__ import annotations

import logging
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
from google import genai
from rich.console import Console

from egregora.agents.avatar import AvatarContext, process_avatar_commands
from egregora.agents.enricher import EnrichmentRuntimeContext, enrich_table
from egregora.agents.model_limits import get_model_context_limit
from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.shared.rag import VectorStore, index_all_media
from egregora.agents.writer import write_posts_for_window
from egregora.config.settings import EgregoraConfig, load_egregora_config
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import OutputSink, UrlContext
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.tracking import record_run
from egregora.database.validation import validate_ir_schema
from egregora.database.views import daily_aggregates_view
from egregora.input_adapters import get_adapter
from egregora.input_adapters.base import MediaMapping
from egregora.input_adapters.whatsapp import extract_commands, filter_egregora_messages
from egregora.knowledge.profiles import filter_opted_out_authors, process_commands
from egregora.ops.media import process_media_for_window
from egregora.orchestration.context import PipelineContext
from egregora.output_adapters.mkdocs import derive_mkdocs_paths
from egregora.output_adapters.mkdocs.paths import compute_site_prefix
from egregora.transformations import create_windows, load_checkpoint, save_checkpoint
from egregora.utils.cache import PipelineCache
from egregora.utils.metrics import UsageTracker
from egregora.utils.quota import QuotaTracker
from egregora.utils.rate_limit import AsyncRateLimit

if TYPE_CHECKING:
    import ibis.expr.types as ir


logger = logging.getLogger(__name__)
console = Console()
__all__ = ["WhatsAppProcessOptions", "process_whatsapp_export", "run"]


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
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None
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
            "rag": base_config.rag.model_copy(
                update={
                    "mode": opts.retrieval_mode,
                    "nprobe": (
                        opts.retrieval_nprobe if opts.retrieval_nprobe is not None else base_config.rag.nprobe
                    ),
                    "overfetch": (
                        opts.retrieval_overfetch
                        if opts.retrieval_overfetch is not None
                        else base_config.rag.overfetch
                    ),
                }
            ),
            **({"models": base_config.models.model_copy(update=models_update)} if models_update else {}),
        },
    )

    return run(
        source="whatsapp",
        input_path=zip_path,
        output_dir=output_dir,
        config=egregora_config,
        api_key=opts.gemini_api_key,
        client=opts.client,
        refresh=opts.refresh,
    )


@dataclass
class PreparedPipelineData:
    """Artifacts produced during dataset preparation."""

    messages_table: ir.Table
    windows_iterator: any
    checkpoint_path: Path
    context: PipelineContext
    enable_enrichment: bool
    embedding_model: str


def _process_single_window(
    window: any, ctx: PipelineContext, *, depth: int = 0
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

    # Enrichment
    if ctx.enable_enrichment:
        logger.info("%s✨ [cyan]Enriching[/] window %s", indent, window_label)
        enriched_table = _perform_enrichment(window_table_processed, media_mapping, ctx)
    else:
        enriched_table = window_table_processed

    if media_mapping:
        for media_doc in media_mapping.values():
            if media_doc.metadata.get("pii_deleted"):
                continue
            try:
                output_sink.persist(media_doc)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to serve media document %s", media_doc.metadata.get("filename"))

    # Write posts
    result = write_posts_for_window(
        enriched_table,
        window.start_time,
        window.end_time,
        ctx,
    )
    post_count = len(result.get("posts", []))
    profile_count = len(result.get("profiles", []))
    logger.info(
        "%s[green]✔ Generated[/] %s posts / %s profiles for %s",
        indent,
        post_count,
        profile_count,
        window_label,
    )

    return {window_label: result}


def _process_window_with_auto_split(
    window: any, ctx: PipelineContext, *, depth: int = 0, max_depth: int = 5
) -> dict[str, dict[str, list[str]]]:
    """Process a window with automatic splitting if prompt exceeds model limit.

    Args:
        window: Window to process
        ctx: Pipeline context
        depth: Current split depth
        max_depth: Maximum split depth before failing

    Returns:
        Dict mapping window labels to {'posts': [...], 'profiles': [...]}

    """
    from egregora.agents.model_limits import PromptTooLargeError
    from egregora.transformations import split_window_into_n_parts

    min_window_size = 5
    results: dict[str, dict[str, list[str]]] = {}
    queue: deque[tuple[any, int]] = deque([(window, depth)])

    while queue:
        current_window, current_depth = queue.popleft()
        indent = "  " * current_depth
        window_label = f"{current_window.start_time:%Y-%m-%d %H:%M} to {current_window.end_time:%H:%M}"

        _warn_if_window_too_small(current_window.size, indent, window_label, min_window_size)
        _ensure_split_depth(current_depth, max_depth, indent, window_label)

        try:
            window_results = _process_single_window(current_window, ctx, depth=current_depth)
        except PromptTooLargeError as error:
            split_work = _split_window_for_retry(
                current_window,
                error,
                current_depth,
                indent,
                split_window_into_n_parts,
            )
            queue.extendleft(reversed(split_work))
            continue

        results.update(window_results)

    return results


def _warn_if_window_too_small(size: int, indent: str, label: str, minimum: int) -> None:
    if size < minimum:
        logger.warning(
            "%s⚠️  Window %s too small to split (%d messages) - attempting anyway",
            indent,
            label,
            size,
        )


def _ensure_split_depth(depth: int, max_depth: int, indent: str, label: str) -> None:
    if depth >= max_depth:
        error_msg = (
            f"Max split depth {max_depth} reached for window {label}. "
            "Window cannot be split enough to fit in model context (possible miscalculation). "
            "Try increasing --max-prompt-tokens or using --use-full-context-window."
        )
        logger.error("%s❌ %s", indent, error_msg)
        raise RuntimeError(error_msg)


def _split_window_for_retry(
    window: any,
    error: Exception,
    depth: int,
    indent: str,
    splitter: any,
) -> list[tuple[any, int]]:
    import math

    estimated_tokens = getattr(error, "estimated_tokens", 0)
    effective_limit = getattr(error, "effective_limit", 1) or 1

    logger.warning(
        "%s⚡ [yellow]Splitting window[/] %s (prompt: %dk tokens > %dk limit)",
        indent,
        f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}",
        estimated_tokens // 1000,
        effective_limit // 1000,
    )

    num_splits = max(1, math.ceil(estimated_tokens / effective_limit))
    logger.info("%s↳ [dim]Splitting into %d parts[/]", indent, num_splits)

    split_windows = splitter(window, num_splits)
    if not split_windows:
        error_msg = (
            f"Cannot split window {window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
            " - all splits would be empty"
        )
        logger.exception("%s❌ %s", indent, error_msg)
        raise RuntimeError(error_msg) from error

    scheduled: list[tuple[any, int]] = []
    for index, split_window in enumerate(split_windows, 1):
        split_label = f"{split_window.start_time:%Y-%m-%d %H:%M} to {split_window.end_time:%H:%M}"
        logger.info(
            "%s↳ [dim]Processing part %d/%d: %s[/]",
            indent,
            index,
            len(split_windows),
            split_label,
        )
        scheduled.append((split_window, depth + 1))

    return scheduled


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
        window_results = _process_window_with_auto_split(window, ctx, depth=0, max_depth=5)
        results.update(window_results)

        # Track max processed timestamp for checkpoint
        if max_processed_timestamp is None or window.end_time > max_processed_timestamp:
            max_processed_timestamp = window.end_time

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
    enrichment_context = EnrichmentRuntimeContext(
        cache=ctx.enrichment_cache,
        output_format=ctx.output_format,
        site_root=ctx.site_root,
        quota=ctx.quota_tracker,
        rate_limit=ctx.rate_limit,
        usage_tracker=ctx.usage_tracker,
    )
    return enrich_table(
        window_table,
        media_mapping,
        ctx.config,
        enrichment_context,
    )


def _is_connection_uri(value: str) -> bool:
    """Return True if the provided value looks like a DB connection URI."""
    if not value:
        return False

    parsed = urlparse(value)
    # Handle Windows drive letters (e.g. C:/path or C:\path)
    return bool(parsed.scheme) and not (len(parsed.scheme) == 1 and value[1:3] in {":/", ":\\"})


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
                normalized_value = f"duckdb:///{fs_path}"

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


def _create_gemini_client(api_key: str | None) -> genai.Client:
    """Create a Gemini client with retry configuration suitable for the pipeline."""
    http_options = genai.types.HttpOptions(
        retryOptions=genai.types.HttpRetryOptions(
            attempts=5,
            initialDelay=2.0,
            maxDelay=15.0,
            expBase=2.0,
            httpStatusCodes=[429, 503],
        )
    )
    return genai.Client(api_key=api_key, http_options=http_options)


def _create_pipeline_context(  # noqa: PLR0913
    output_dir: Path,
    config: EgregoraConfig,
    api_key: str | None,
    client: genai.Client | None,
    run_id: uuid.UUID,
    start_time: datetime,
    source_type: str,
    input_path: Path,
    refresh: str | None = None,
) -> tuple[PipelineContext, any, any]:
    """Create pipeline context with all resources and configuration.

    Args:
        output_dir: Output directory for the pipeline
        config: Egregora configuration
        api_key: Google API key
        client: Optional existing Gemini client
        run_id: Unique run identifier
        start_time: Run start timestamp
        source_type: Source type (e.g., "whatsapp", "slack")
        input_path: Path to input file
        refresh: Optional comma-separated list of cache tiers to refresh

    Returns:
        Tuple of (PipelineContext, pipeline_backend, runs_backend)
        The backends are returned for cleanup by the context manager.

    """
    resolved_output = output_dir.expanduser().resolve()

    refresh_tiers = {r.strip().lower() for r in (refresh or "").split(",") if r.strip()}
    site_paths = _resolve_site_paths_or_raise(resolved_output, config)
    _runtime_db_uri, pipeline_backend, runs_backend = _create_database_backends(
        site_paths["site_root"], config
    )

    # Initialize database tables (CREATE TABLE IF NOT EXISTS)
    from egregora.database import initialize_database

    initialize_database(pipeline_backend)

    client_instance = client or _create_gemini_client(api_key)
    cache_dir = Path(".egregora-cache") / site_paths["site_root"].name
    cache = PipelineCache(cache_dir, refresh_tiers=refresh_tiers)
    site_paths["egregora_dir"].mkdir(parents=True, exist_ok=True)
    db_file = site_paths["egregora_dir"] / "app.duckdb"
    storage = DuckDBStorageManager(db_path=db_file)

    rag_store = None
    if config.rag.enabled:
        rag_dir = site_paths["site_root"] / ".egregora" / "rag"
        rag_dir.mkdir(parents=True, exist_ok=True)
        rag_store = VectorStore(rag_dir / "chunks.parquet", storage=storage)

    annotations_store = AnnotationStore(storage)

    from egregora.orchestration.context import PipelineConfig, PipelineState

    quota_tracker = QuotaTracker(site_paths["egregora_dir"], config.quota.daily_llm_requests)
    rate_limit = AsyncRateLimit(config.quota.per_second_limit)

    url_ctx = UrlContext(
        base_url="",
        site_prefix=compute_site_prefix(site_paths["site_root"], site_paths["docs_dir"]),
        base_path=site_paths["site_root"],
    )

    config_obj = PipelineConfig(
        config=config,
        output_dir=resolved_output,
        site_root=site_paths["site_root"],
        docs_dir=site_paths["docs_dir"],
        posts_dir=site_paths["posts_dir"],
        profiles_dir=site_paths["profiles_dir"],
        media_dir=site_paths["media_dir"],
        url_context=url_ctx,
    )

    state = PipelineState(
        run_id=run_id,
        start_time=start_time,
        source_type=source_type,
        input_path=input_path,
        client=client_instance,
        storage=storage,
        enrichment_cache=cache.enrichment,
        cache=cache,
        rag_store=rag_store,
        annotations_store=annotations_store,
        quota_tracker=quota_tracker,
        rate_limit=rate_limit,
        usage_tracker=UsageTracker(),
    )

    ctx = PipelineContext(config_obj, state)

    return ctx, pipeline_backend, runs_backend


@contextmanager
def _pipeline_environment(  # noqa: PLR0913
    output_dir: Path,
    config: EgregoraConfig,
    api_key: str | None,
    client: genai.Client | None,
    run_id: uuid.UUID,
    start_time: datetime,
    source_type: str,
    input_path: Path,
    refresh: str | None = None,
) -> any:
    """Context manager that provisions and tears down pipeline resources.

    Args:
        output_dir: Output directory for the pipeline
        config: Egregora configuration
        api_key: Google API key
        client: Optional existing Gemini client
        run_id: Unique run identifier
        start_time: Run start timestamp
        source_type: Source type (e.g., "whatsapp", "slack")
        input_path: Path to input file
        refresh: Optional comma-separated list of cache tiers to refresh

    Yields:
        Tuple of (PipelineContext, runs_backend) for use in the pipeline

    """
    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None
    ctx, pipeline_backend, runs_backend = _create_pipeline_context(
        output_dir, config, api_key, client, run_id, start_time, source_type, input_path, refresh
    )

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
    """Parse source and validate schema.

    Args:
        adapter: Source adapter instance
        input_path: Path to input file
        timezone: Timezone string
        output_adapter: Optional output adapter (used by adapters that reprocess existing sites)

    Returns:
        messages_table: Validated messages table

    Raises:
        ValueError: If schema validation fails

    Note:
        Currently validates against CONVERSATION_SCHEMA (MESSAGE_SCHEMA).
        IR_MESSAGE_SCHEMA implementation is planned for future release.
        See docs/ux-testing-2025-11-15.md for details.

    """
    logger.info("[bold cyan]📦 Parsing with adapter:[/] %s", adapter.source_name)
    messages_table = adapter.parse(input_path, timezone=timezone, output_adapter=output_adapter)

    # Validate IR schema (raises SchemaError if invalid)
    validate_ir_schema(messages_table)

    logger.debug("IR schema validation passed: %s", messages_table.schema())
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
    input_path: Path,
    config: EgregoraConfig,
    ctx: PipelineContext,
    output_dir: Path,
) -> PreparedPipelineData:
    """Prepare messages, filters, and windowing context for processing.

    Args:
        adapter: Input adapter instance
        input_path: Path to input file
        config: Egregora configuration
        ctx: Pipeline context
        output_dir: Output directory

    Returns:
        PreparedPipelineData with messages table, windows iterator, and updated context

    """
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

    from egregora.output_adapters import create_output_format

    output_format = create_output_format(output_dir, format_type=config.output.format)
    ctx = ctx.with_output_format(output_format)

    messages_table = _parse_and_validate_source(adapter, input_path, timezone, output_adapter=output_format)
    _setup_content_directories(ctx)
    messages_table = _process_commands_and_avatars(messages_table, ctx, vision_model)

    checkpoint_path = ctx.site_root / ".egregora" / "checkpoint.json"
    messages_table = _apply_filters(
        messages_table,
        ctx,
        from_date,
        to_date,
        checkpoint_path,
        checkpoint_enabled=config.pipeline.checkpoint_enabled,
    )

    logger.info("🎯 [bold cyan]Creating windows:[/] step_size=%s, unit=%s", step_size, step_unit)
    windows_iterator = create_windows(
        messages_table,
        step_size=step_size,
        step_unit=step_unit,
        overlap_ratio=overlap_ratio,
        max_window_time=max_window_time,
    )

    # Update context with adapter
    ctx = ctx.with_adapter(adapter)

    if config.rag.enabled:
        logger.info("[bold cyan]📚 Indexing existing documents into RAG...[/]")
        try:
            from egregora.agents.shared.rag import index_documents_for_rag

            indexed_count = index_documents_for_rag(
                output_format,
                ctx.site_root / ".egregora" / "rag",
                ctx.storage,
                embedding_model=embedding_model,
            )
            if indexed_count > 0:
                logger.info("[green]✓ Indexed[/] %s documents into RAG", indexed_count)
            else:
                logger.info("[dim]No new documents to index[/]")
        except Exception:
            logger.exception("[yellow]⚠️  Failed to index documents into RAG[/]")

    return PreparedPipelineData(
        messages_table=messages_table,
        windows_iterator=windows_iterator,
        checkpoint_path=checkpoint_path,
        context=ctx,
        enable_enrichment=enable_enrichment,
        embedding_model=embedding_model,
    )


def _index_media_into_rag(
    enable_enrichment: bool,  # noqa: FBT001
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

    logger.info("[bold cyan]📚 Indexing media into RAG...[/]")
    try:
        rag_dir = ctx.site_root / ".egregora" / "rag"
        store = VectorStore(rag_dir / "chunks.parquet", storage=ctx.storage)
        media_chunks = index_all_media(ctx.docs_dir, store, embedding_model=embedding_model)
        if media_chunks > 0:
            logger.info("[green]✓ Indexed[/] %s media chunks into RAG", media_chunks)
        else:
            logger.info("[yellow]No media enrichments to index[/]")
    except Exception:
        logger.exception("[red]Failed to index media into RAG[/]")


def _generate_statistics_page(messages_table: ir.Table, ctx: PipelineContext) -> None:
    """Generate statistics page from conversation data.

    Creates a POST-type document with daily activity statistics and persists it
    via the output adapter. Skips generation if messages table is empty.

    Args:
        messages_table: Complete messages table (before windowing). Must conform
            to IR_MESSAGE_SCHEMA.
        ctx: Pipeline context with output adapter for persistence.

    Side Effects:
        - Writes statistics document to ctx.output_format.persist()
        - Logs info/warning/error messages

    Raises:
        Does not raise exceptions - errors are caught and logged.

    """
    logger.info("[bold cyan]📊 Generating statistics page...[/]")

    # Compute daily aggregates (stays as Ibis Table)
    stats_table = daily_aggregates_view(messages_table)

    # Check if empty using Ibis
    row_count = stats_table.count().to_pyarrow().as_py()
    if row_count == 0:
        logger.warning("No statistics data available - skipping statistics page")
        return

    # Calculate totals using Ibis
    total_messages = messages_table.count().to_pyarrow().as_py()
    total_authors = messages_table.author_uuid.nunique().to_pyarrow().as_py()

    # Get date range using Ibis aggregation
    date_range = stats_table.aggregate(
        [stats_table.day.min().name("min_day"), stats_table.day.max().name("max_day")]
    ).to_pyarrow()

    min_date = date_range["min_day"][0].as_py()
    max_date = date_range["max_day"][0].as_py()

    # Extract date-only strings for clean slugs (avoid timestamp in URL)
    min_date_str = min_date.date().isoformat() if hasattr(min_date, "date") else str(min_date)[:10]
    max_date_str = max_date.date().isoformat() if hasattr(max_date, "date") else str(max_date)[:10]

    # Build Markdown content
    content_lines = [
        "# Conversation Statistics",
        "",
        "This page provides an overview of activity in this conversation archive.",
        "",
        "## Summary",
        "",
        f"- **Total Messages**: {total_messages:,}",
        f"- **Unique Authors**: {total_authors}",
        f"- **Date Range**: {min_date_str} to {max_date_str}",
        "",
        "## Daily Activity",
        "",
        "| Date | Messages | Active Authors | First Message | Last Message |",
        "|------|----------|----------------|---------------|--------------|",
    ]

    # Convert to PyArrow (not pandas) for iteration
    stats_arrow = stats_table.to_pyarrow()
    for row in stats_arrow.to_pylist():
        date_str = row["day"].strftime("%Y-%m-%d")
        msg_count = f"{row['message_count']:,}"
        author_count = row["unique_authors"]
        first_time = row["first_message"].strftime("%H:%M")
        last_time = row["last_message"].strftime("%H:%M")
        content_lines.append(f"| {date_str} | {msg_count} | {author_count} | {first_time} | {last_time} |")

    content = "\n".join(content_lines)

    # Create Document with data-derived date (not current timestamp)
    doc = Document(
        content=content,
        type=DocumentType.POST,
        metadata={
            "title": "Conversation Statistics",
            "date": max_date_str,  # Use YYYY-MM-DD format for clean URLs
            "slug": "statistics",
            "tags": ["meta", "statistics"],
            "summary": "Overview of conversation activity and daily message volume",
        },
    )

    # Persist document with error handling
    try:
        if ctx.output_format:
            ctx.output_format.persist(doc)
            logger.info("[green]✓ Statistics page generated[/]")
        else:
            logger.warning("Output format not initialized - cannot save statistics page")
    except Exception:
        logger.exception("[red]Failed to generate statistics page[/]")


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


def _apply_filters(  # noqa: C901, PLR0913, PLR0912
    messages_table: ir.Table,
    ctx: PipelineContext,
    from_date: date_type | None,
    to_date: date_type | None,
    checkpoint_path: Path,
    checkpoint_enabled: bool = False,  # noqa: FBT001, FBT002
) -> ir.Table:
    """Apply all filters: egregora messages, opted-out users, date range, checkpoint resume.

    Args:
        messages_table: Input messages table
        ctx: Pipeline context
        from_date: Filter start date (inclusive)
        to_date: Filter end date (inclusive)
        checkpoint_path: Path to checkpoint file
        checkpoint_enabled: Enable incremental processing (default: False)

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
    if from_date or to_date:
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

    # Checkpoint-based resume logic (OPT-IN)
    if checkpoint_enabled:
        checkpoint = load_checkpoint(checkpoint_path)
        if checkpoint and "last_processed_timestamp" in checkpoint:
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
        else:
            logger.info("🆕 [cyan]Starting fresh[/] (checkpoint enabled, but no checkpoint found)")
    else:
        logger.info("🆕 [cyan]Full rebuild[/] (checkpoint disabled - default behavior)")

    return messages_table


def run(  # noqa: PLR0913
    source: str,
    input_path: Path,
    output_dir: Path,
    config: EgregoraConfig,
    *,
    api_key: str | None = None,
    client: genai.Client | None = None,
    refresh: str | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Run the complete write pipeline workflow.

    Args:
        source: Source type (e.g., "whatsapp", "slack")
        input_path: Path to input file
        output_dir: Output directory
        config: Egregora configuration
        api_key: Optional Google API key
        client: Optional existing Gemini client
        refresh: Optional comma-separated list of cache tiers to refresh

    Returns:
        Dict mapping window labels to {'posts': [...], 'profiles': [...]}

    """
    logger.info("[bold cyan]🚀 Starting pipeline for source:[/] %s", source)
    adapter = get_adapter(source)

    # Generate run ID and timestamp for tracking
    run_id = uuid.uuid4()
    started_at = datetime.now(UTC)

    with _pipeline_environment(
        output_dir, config, api_key, client, run_id, started_at, source, input_path, refresh
    ) as (ctx, runs_backend):
        # Get DuckDB connection from Ibis backend for run tracking
        runs_conn = getattr(runs_backend, "con", None)
        if runs_conn is None:
            logger.warning("Unable to access DuckDB connection for run tracking - runs will not be recorded")

        # Record run start
        if runs_conn is not None:
            try:
                record_run(
                    conn=runs_conn,
                    run_id=run_id,
                    stage="write",
                    status="running",
                    started_at=started_at,
                )
            except Exception as exc:  # noqa: BLE001 - Don't break pipeline for tracking failures
                logger.debug("Failed to record run start: %s", exc)

        try:
            dataset = _prepare_pipeline_data(adapter, input_path, config, ctx, output_dir)
            results, max_processed_timestamp = _process_all_windows(dataset.windows_iterator, dataset.context)
            _index_media_into_rag(
                dataset.enable_enrichment,
                results,
                dataset.context,
                dataset.embedding_model,
            )
            # Save checkpoint first (critical path)
            _save_checkpoint(results, max_processed_timestamp, dataset.checkpoint_path)

            # Generate statistics page (non-critical, isolated)
            try:
                _generate_statistics_page(dataset.messages_table, dataset.context)
            except Exception:
                logger.exception("[red]Failed to generate statistics page (non-critical)[/]")

            # Calculate metrics
            finished_at = datetime.now(UTC)
            total_posts = sum(len(r.get("posts", [])) for r in results.values())
            total_profiles = sum(len(r.get("profiles", [])) for r in results.values())
            num_windows = len(results)

            # Update run to completed
            if runs_conn is not None:
                try:
                    duration_seconds = (finished_at - started_at).total_seconds()
                    runs_conn.execute(
                        """
                        UPDATE runs
                        SET status = 'completed',
                            finished_at = ?,
                            duration_seconds = ?,
                            rows_out = ?
                        WHERE run_id = ?
                        """,
                        [finished_at, duration_seconds, total_posts + total_profiles, str(run_id)],
                    )
                    logger.debug(
                        "Recorded pipeline run: %s (posts=%d, profiles=%d, windows=%d)",
                        run_id,
                        total_posts,
                        total_profiles,
                        num_windows,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to record run completion: %s", exc)

            logger.info("[bold green]🎉 Pipeline completed successfully![/]")

        except Exception as exc:
            # Update run to failed
            finished_at = datetime.now(UTC)
            if runs_conn is not None:
                try:
                    duration_seconds = (finished_at - started_at).total_seconds()
                    error_msg = f"{type(exc).__name__}: {exc!s}"
                    runs_conn.execute(
                        """
                        UPDATE runs
                        SET status = 'failed',
                            finished_at = ?,
                            duration_seconds = ?,
                            error = ?
                        WHERE run_id = ?
                        """,
                        [finished_at, duration_seconds, error_msg[:500], str(run_id)],
                    )
                except Exception as tracking_exc:  # noqa: BLE001
                    logger.debug("Failed to record run failure: %s", tracking_exc)
            raise  # Re-raise original exception

        return results
