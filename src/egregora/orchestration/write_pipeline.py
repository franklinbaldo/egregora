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
import math
import tempfile
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

from egregora.agents.model_limits import get_model_context_limit
from egregora.agents.shared.author_profiles import filter_opted_out_authors, process_commands
from egregora.agents.shared.rag import VectorStore, index_all_media
from egregora.agents.writer import WriterConfig, write_posts_for_window
from egregora.config import get_model_for_task
from egregora.config.settings import EgregoraConfig, load_egregora_config
from egregora.database import RUN_EVENTS_SCHEMA
from egregora.database.tracking import fingerprint_window, get_git_commit_sha
from egregora.database.validation import validate_ir_schema
from egregora.enrichment import enrich_table
from egregora.enrichment.avatar import AvatarContext, process_avatar_commands
from egregora.enrichment.runners import EnrichmentRuntimeContext
from egregora.input_adapters import get_adapter
from egregora.input_adapters.whatsapp.parser import extract_commands, filter_egregora_messages
from egregora.output_adapters.mkdocs import resolve_site_paths
from egregora.transformations import create_windows, load_checkpoint, save_checkpoint
from egregora.transformations.media import process_media_for_window
from egregora.utils.cache import EnrichmentCache

if TYPE_CHECKING:
    import ibis.expr.types as ir
logger = logging.getLogger(__name__)
__all__ = ["WhatsAppProcessOptions", "process_whatsapp_export", "run"]


@dataclass(slots=True)
class WhatsAppProcessOptions:
    """Overrides applied when processing WhatsApp exports via :func:`run`."""

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


def process_whatsapp_export(
    zip_path: Path,
    output_dir: Path = Path("output"),
    *,
    options: WhatsAppProcessOptions | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """High-level helper for processing WhatsApp ZIP exports using :func:`run`."""
    resolved_options = options or WhatsAppProcessOptions()
    output_dir = output_dir.expanduser().resolve()
    site_paths = resolve_site_paths(output_dir)

    base_config = load_egregora_config(site_paths.site_root)
    timezone = resolved_options.timezone
    timezone_str = str(timezone) if timezone else None

    pipeline_overrides = {
        "step_size": resolved_options.step_size,
        "step_unit": resolved_options.step_unit,
        "overlap_ratio": resolved_options.overlap_ratio,
        "timezone": timezone_str,
        "from_date": (resolved_options.from_date.isoformat() if resolved_options.from_date else None),
        "to_date": resolved_options.to_date.isoformat() if resolved_options.to_date else None,
        "batch_threshold": resolved_options.batch_threshold,
        "max_prompt_tokens": resolved_options.max_prompt_tokens,
        "use_full_context_window": resolved_options.use_full_context_window,
    }

    rag_overrides = {
        "mode": resolved_options.retrieval_mode,
        "nprobe": (
            resolved_options.retrieval_nprobe
            if resolved_options.retrieval_nprobe is not None
            else base_config.rag.nprobe
        ),
        "overfetch": (
            resolved_options.retrieval_overfetch
            if resolved_options.retrieval_overfetch is not None
            else base_config.rag.overfetch
        ),
    }

    egregora_config = base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(update=pipeline_overrides),
            "enrichment": base_config.enrichment.model_copy(
                update={"enabled": resolved_options.enable_enrichment}
            ),
            "rag": base_config.rag.model_copy(update=rag_overrides),
        },
    )

    return run(
        source="whatsapp",
        input_path=zip_path,
        output_dir=output_dir,
        config=egregora_config,
        api_key=resolved_options.gemini_api_key,
        model_override=resolved_options.model,
        client=client,
    )


@dataclass
class WindowProcessingContext:
    """Context for window processing to reduce parameter passing."""

    adapter: any
    input_path: Path
    site_paths: any
    posts_dir: Path
    profiles_dir: Path
    config: EgregoraConfig
    enrichment_cache: EnrichmentCache
    output_format: any
    enable_enrichment: bool
    cli_model_override: str | None
    retrieval_mode: str
    retrieval_nprobe: int
    retrieval_overfetch: int
    client: genai.Client


def _process_single_window(
    window: any, ctx: WindowProcessingContext, *, depth: int = 0
) -> dict[str, dict[str, list[str]]]:
    """Process a single window with media extraction, enrichment, and post writing.

    Args:
        window: Window to process
        ctx: Window processing context
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
    temp_prefix = f"egregora-media-{window.start_time:%Y%m%d_%H%M%S}-"
    with tempfile.TemporaryDirectory(prefix=temp_prefix) as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        window_table_processed, media_mapping = process_media_for_window(
            window_table=window_table,
            adapter=ctx.adapter,
            media_dir=ctx.site_paths.media_dir,
            temp_dir=temp_dir,
            docs_dir=ctx.site_paths.docs_dir,
            posts_dir=ctx.posts_dir,
            zip_path=ctx.input_path,
        )

    # Enrichment
    if ctx.enable_enrichment:
        logger.info("%s✨ [cyan]Enriching[/] window %s", indent, window_label)
        enriched_table = _perform_enrichment(
            window_table_processed,
            media_mapping,
            ctx.config,
            ctx.enrichment_cache,
            ctx.site_paths,
            ctx.posts_dir,
            ctx.output_format,
        )
    else:
        enriched_table = window_table_processed

    # Write posts
    writer_config = WriterConfig(
        output_dir=ctx.posts_dir,
        profiles_dir=ctx.profiles_dir,
        rag_dir=ctx.site_paths.rag_dir,
        site_root=ctx.site_paths.site_root,
        egregora_config=ctx.config,
        cli_model=ctx.cli_model_override,
        enable_rag=True,
        retrieval_mode=ctx.retrieval_mode,
        retrieval_nprobe=ctx.retrieval_nprobe,
        retrieval_overfetch=ctx.retrieval_overfetch,
    )

    result = write_posts_for_window(
        enriched_table, window.start_time, window.end_time, ctx.client, writer_config
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


def _warn_if_window_too_small(window_count: int, indent: str, window_label: str) -> None:
    """Log a warning when a split attempt happens on a very small window."""
    min_window_size = 5
    if window_count < min_window_size:
        logger.warning(
            "%s⚠️  Window %s too small to split (%d messages) - attempting anyway",
            indent,
            window_label,
            window_count,
        )


def _ensure_split_depth(depth: int, max_depth: int, indent: str, window_label: str) -> None:
    """Raise if recursive split depth exceeds the configured safety limit."""
    if depth < max_depth:
        return

    error_msg = (
        f"Max split depth {max_depth} reached for window {window_label}. "
        "Window cannot be split enough to fit in model context (possible miscalculation). "
        "Try increasing --max-prompt-tokens or using --use-full-context-window."
    )
    logger.error("%s❌ %s", indent, error_msg)
    raise RuntimeError(error_msg)


def _plan_window_splits(
    window: any,
    error: Exception,
    indent: str,
    window_label: str,
) -> list:
    """Determine how a window should be split after exceeding prompt limits."""
    from egregora.agents.model_limits import PromptTooLargeError
    from egregora.transformations import split_window_into_n_parts

    if not isinstance(error, PromptTooLargeError):  # pragma: no cover - defensive guard
        raise error

    logger.warning(
        "%s⚡ [yellow]Splitting window[/] %s (prompt: %dk tokens > %dk limit)",
        indent,
        window_label,
        error.estimated_tokens // 1000,
        error.effective_limit // 1000,
    )

    num_splits = max(2, math.ceil(error.estimated_tokens / error.effective_limit))
    logger.info("%s↳ [dim]Splitting into %d parts[/]", indent, num_splits)

    split_windows = split_window_into_n_parts(window, num_splits)
    if not split_windows:
        error_msg = f"Cannot split window {window_label} - all splits would be empty"
        logger.exception("%s❌ %s", indent, error_msg)
        raise RuntimeError(error_msg) from error

    return split_windows


def _process_window_with_auto_split(
    window: any, ctx: WindowProcessingContext, *, depth: int = 0, max_depth: int = 5
) -> dict[str, dict[str, list[str]]]:
    """Process a window with automatic splitting if prompt exceeds model limit."""
    from egregora.agents.model_limits import PromptTooLargeError

    combined_results: dict[str, dict[str, list[str]]] = {}
    queue: deque[tuple[any, int]] = deque([(window, depth)])

    while queue:
        current_window, current_depth = queue.popleft()
        indent = "  " * current_depth
        window_label = f"{current_window.start_time:%Y-%m-%d %H:%M} to {current_window.end_time:%H:%M}"
        window_count = current_window.size

        _warn_if_window_too_small(window_count, indent, window_label)
        _ensure_split_depth(current_depth, max_depth, indent, window_label)

        try:
            window_results = _process_single_window(current_window, ctx, depth=current_depth)
        except PromptTooLargeError as exc:
            split_windows = _plan_window_splits(current_window, exc, indent, window_label)
            total_parts = len(split_windows)
            for index, split_window in enumerate(split_windows, 1):
                split_label = f"{split_window.start_time:%Y-%m-%d %H:%M} to {split_window.end_time:%H:%M}"
                logger.info(
                    "%s↳ [dim]Processing part %d/%d: %s[/]",
                    indent,
                    index,
                    total_parts,
                    split_label,
                )
                queue.append((split_window, current_depth + 1))
            continue

        combined_results.update(window_results)

    return combined_results


RUN_EVENTS_TABLE_NAME = "run_events"


def _ensure_run_events_table_exists(runs_backend: any) -> None:
    """Create the run_events tracking table if it is missing for the backend."""
    try:
        if RUN_EVENTS_TABLE_NAME in set(runs_backend.list_tables()):
            return
    except Exception as exc:  # noqa: BLE001 - Graceful degradation for any backend
        logger.debug("Unable to list tables for runs backend: %s", exc)

    try:
        runs_backend.create_table(RUN_EVENTS_TABLE_NAME, schema=RUN_EVENTS_SCHEMA)
    except Exception as exc:  # noqa: BLE001 - Graceful degradation for any backend
        # If the table already exists (created externally), retrieving it should
        # succeed; otherwise re-raise to surface the configuration issue.
        try:
            runs_backend.table(RUN_EVENTS_TABLE_NAME)
        except Exception as lookup_err:
            msg = "Failed to ensure run_events tracking table exists"
            raise RuntimeError(msg) from lookup_err
        else:
            logger.debug("Run events table already present: %s", exc)


def _record_run_event(runs_backend: any, event: dict[str, object]) -> None:
    """Record a run status event using event-sourced pattern (append-only).

    Each status change is a new event with unique event_id. No UPDATE/DELETE needed.
    Works with any backend supporting INSERT, providing full audit trail.

    Args:
        runs_backend: Ibis backend for run tracking
        event: Event dict matching RUN_EVENTS_SCHEMA (must include event_id, run_id, status, timestamp)

    Note:
        Failures are logged but don't break the pipeline (observability-only).

    """
    try:
        _ensure_run_events_table_exists(runs_backend)

        rows = ibis.memtable([event], schema=RUN_EVENTS_SCHEMA)
        insert_fn = getattr(runs_backend, "insert", None)
        if not callable(insert_fn):
            logger.debug(
                "Run tracking unavailable: backend %s doesn't support insert()",
                type(runs_backend).__name__,
            )
            return

        insert_fn(RUN_EVENTS_TABLE_NAME, rows)
    except Exception as exc:  # noqa: BLE001 - Observability failures don't break pipeline
        logger.debug("Failed to record run event: %s", exc)
        # Don't break pipeline for observability failures


def _resolve_context_token_limit(config: EgregoraConfig, cli_model_override: str | None = None) -> int:
    """Resolve the effective context window token limit for the writer model.

    Args:
        config: Egregora configuration with model settings.
        cli_model_override: Optional CLI model override to respect.

    Returns:
        Maximum number of prompt tokens available for a window.

    """
    use_full_window = getattr(config.pipeline, "use_full_context_window", False)

    if use_full_window:
        writer_model = get_model_for_task("writer", config, cli_override=cli_model_override)
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


def _calculate_max_window_size(config: EgregoraConfig, cli_model_override: str | None = None) -> int:
    """Calculate maximum window size based on LLM context window.

    Uses rough heuristic: 5 tokens per message average.
    Leaves 20% buffer for prompt overhead (system prompt, tools, etc.).

    Args:
        config: Egregora configuration with model settings
        cli_model_override: Optional CLI model override for the writer model

    Returns:
        Maximum number of messages per window

    Example:
        >>> config.pipeline.max_prompt_tokens = 100_000
        >>> _calculate_max_window_size(config)
        16000  # (100k * 0.8) / 5

    """
    max_tokens = _resolve_context_token_limit(config, cli_model_override)
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
    windows_iterator: any, ctx: WindowProcessingContext, runs_backend: any
) -> dict[str, dict[str, list[str]]]:
    """Process all windows with tracking and error handling.

    Args:
        windows_iterator: Iterator of Window objects
        ctx: Window processing context
        runs_backend: Ibis backend for run tracking

    Returns:
        Dict mapping window labels to {'posts': [...], 'profiles': [...]}

    """
    results = {}

    # Calculate max window size from LLM context (once)
    max_window_size = _calculate_max_window_size(ctx.config, ctx.cli_model_override)
    effective_token_limit = _resolve_context_token_limit(ctx.config, ctx.cli_model_override)
    logger.debug(
        "Max window size: %d messages (based on %d token context)",
        max_window_size,
        effective_token_limit,
    )

    for window in windows_iterator:
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

        # Track window processing (event-sourced)
        run_id = uuid.uuid4()
        started_at = datetime.now(UTC)

        # Record "started" event
        try:
            input_fingerprint = fingerprint_window(window)

            start_event = {
                "event_id": uuid.uuid4(),
                "run_id": run_id,
                "tenant_id": None,
                "stage": f"window_{window.window_index}",
                "status": "started",
                "error": None,
                "input_fingerprint": input_fingerprint,
                "code_ref": get_git_commit_sha(),
                "config_hash": None,
                "timestamp": started_at,
                "rows_in": window.size,
                "rows_out": None,
                "duration_seconds": None,
                "llm_calls": None,
                "tokens": None,
                "trace_id": None,
            }

            _record_run_event(runs_backend, start_event)
        except Exception as e:  # noqa: BLE001 - Observability failures don't break pipeline
            logger.warning("Failed to record run start event: %s", e)

        # Process window
        try:
            window_results = _process_window_with_auto_split(window, ctx, depth=0, max_depth=5)
            results.update(window_results)

            # Record "completed" event
            finished_at = datetime.now(UTC)
            posts_count = sum(len(r.get("posts", [])) for r in window_results.values())
            profiles_count = sum(len(r.get("profiles", [])) for r in window_results.values())

            try:
                completion_event = {
                    "event_id": uuid.uuid4(),  # New event ID
                    "run_id": run_id,  # Same run ID
                    "tenant_id": None,
                    "stage": f"window_{window.window_index}",
                    "status": "completed",
                    "error": None,
                    "input_fingerprint": None,
                    "code_ref": get_git_commit_sha(),
                    "config_hash": None,
                    "timestamp": finished_at,
                    "rows_in": None,
                    "rows_out": posts_count + profiles_count,
                    "duration_seconds": (finished_at - started_at).total_seconds(),
                    "llm_calls": None,
                    "tokens": None,
                    "trace_id": None,
                }

                _record_run_event(runs_backend, completion_event)

                logger.debug(
                    "📊 Tracked run %s: %s posts, %s profiles",
                    str(run_id)[:8],
                    posts_count,
                    profiles_count,
                )
            except Exception as e:  # noqa: BLE001 - Observability failures don't break pipeline
                logger.warning("Failed to record run completion event: %s", e)

        except Exception as e:
            # Record "failed" event
            finished_at = datetime.now(UTC)
            error_msg = f"{type(e).__name__}: {e!s}"

            try:
                failure_event = {
                    "event_id": uuid.uuid4(),  # New event ID
                    "run_id": run_id,  # Same run ID
                    "tenant_id": None,
                    "stage": f"window_{window.window_index}",
                    "status": "failed",
                    "error": error_msg,
                    "input_fingerprint": None,
                    "code_ref": get_git_commit_sha(),
                    "config_hash": None,
                    "timestamp": finished_at,
                    "rows_in": None,
                    "rows_out": None,
                    "duration_seconds": (finished_at - started_at).total_seconds(),
                    "llm_calls": None,
                    "tokens": None,
                    "trace_id": None,
                }

                _record_run_event(runs_backend, failure_event)
            except Exception as update_err:  # noqa: BLE001 - Observability failures don't break pipeline
                logger.warning("Failed to record run failure event: %s", update_err)

            # Re-raise the original exception
            raise

    return results


def _perform_enrichment(
    window_table: ir.Table,
    media_mapping: dict[str, Path],
    config: EgregoraConfig,
    enrichment_cache: EnrichmentCache,
    site_paths: any,
    posts_dir: Path,
    output_format: any,
) -> ir.Table:
    """Execute enrichment for a window's table.

    Phase 3: Extracted to eliminate duplication in resume/non-resume branches.

    Args:
        window_table: Table to enrich
        media_mapping: Media file mapping
        config: Egregora configuration
        enrichment_cache: Enrichment cache instance
        site_paths: Site path configuration
        posts_dir: Posts output directory
        output_format: OutputAdapter instance for storage protocol access

    Returns:
        Enriched table

    """
    enrichment_context = EnrichmentRuntimeContext(
        cache=enrichment_cache,
        docs_dir=site_paths.docs_dir,
        posts_dir=posts_dir,
        output_format=output_format,
        site_root=site_paths.site_root,
    )
    return enrich_table(
        window_table,
        media_mapping,
        config,
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


def _resolve_pipeline_site_paths(output_dir: Path, config: EgregoraConfig) -> SitePaths:
    """Resolve site paths for the configured output format."""
    output_dir = output_dir.expanduser().resolve()
    base_paths = resolve_site_paths(output_dir)

    if config.output.format != "eleventy-arrow":
        return base_paths

    from egregora.output_adapters import create_output_format

    output_format = create_output_format(output_dir, format_type=config.output.format)
    site_config = output_format.resolve_paths(output_dir)
    return SitePaths(
        site_root=site_config.site_root,
        mkdocs_path=None,
        egregora_dir=base_paths.egregora_dir,
        config_path=base_paths.config_path,
        mkdocs_config_path=base_paths.mkdocs_config_path,
        prompts_dir=base_paths.prompts_dir,
        rag_dir=base_paths.rag_dir,
        cache_dir=base_paths.cache_dir,
        docs_dir=site_config.docs_dir,
        blog_dir=base_paths.blog_dir,
        posts_dir=site_config.posts_dir,
        profiles_dir=site_config.profiles_dir,
        media_dir=site_config.media_dir,
        rankings_dir=base_paths.rankings_dir,
        enriched_dir=base_paths.enriched_dir,
    )


def _resolve_site_paths_or_raise(output_dir: Path, config: EgregoraConfig) -> SitePaths:
    """Resolve site paths and validate required scaffolding exists."""
    site_paths = _resolve_pipeline_site_paths(output_dir, config)
    format_type = config.output.format

    if format_type != "eleventy-arrow":
        if not site_paths.mkdocs_path or not site_paths.mkdocs_path.exists():
            msg = (
                f"No mkdocs.yml found for site at {output_dir}. "
                "Run 'egregora init <site-dir>' before processing exports."
            )
            raise ValueError(msg)

        if not site_paths.docs_dir.exists():
            msg = (
                f"Docs directory not found: {site_paths.docs_dir}. "
                "Re-run 'egregora init' to scaffold the MkDocs project."
            )
            raise ValueError(msg)
    elif not site_paths.docs_dir.exists():
        msg = (
            "Eleventy content directory not found at "
            f"{site_paths.docs_dir}. Run 'egregora init <site-dir> --output-format eleventy-arrow' "
            "to scaffold the project before processing exports."
        )
        raise ValueError(msg)

    return site_paths


def _setup_pipeline_environment(
    output_dir: Path, config: EgregoraConfig, api_key: str | None, model_override: str | None
) -> tuple[
    any,
    str,
    any,
    any,
    str | None,
    genai.Client,
    EnrichmentCache,
]:
    """Set up pipeline environment including paths, backends, and clients.

    Args:
        output_dir: Output directory for generated content
        config: Egregora configuration
        api_key: Google Gemini API key (optional override)
        model_override: Model override for CLI --model flag

    Returns:
        Tuple of (site_paths, runtime_db_uri, pipeline_backend, runs_backend, model_override, client, enrichment_cache)

    Raises:
        ValueError: If mkdocs.yml or docs directory not found

    """
    output_dir = output_dir.expanduser().resolve()
    site_paths = _resolve_site_paths_or_raise(output_dir, config)

    # Setup database backends (Ibis-based, database-agnostic)
    runtime_db_uri, backend, runs_backend = _create_database_backends(site_paths.site_root, config)

    # Setup Gemini client
    # Configure aggressive retry options to handle rate limits efficiently
    http_options = genai.types.HttpOptions(
        retryOptions=genai.types.HttpRetryOptions(
            attempts=5,  # Max retry attempts
            initialDelay=2.0,  # Start with 2s delay
            maxDelay=15.0,  # Cap at 15s (reduced from default 60s)
            expBase=2.0,  # Exponential backoff multiplier
            httpStatusCodes=[429, 503],  # Retry on rate limit and service unavailable
        )
    )
    client = genai.Client(api_key=api_key, http_options=http_options)

    # Setup enrichment cache
    cache_dir = Path(".egregora-cache") / site_paths.site_root.name
    enrichment_cache = EnrichmentCache(cache_dir)

    return (
        site_paths,
        runtime_db_uri,
        backend,
        runs_backend,
        model_override,
        client,
        enrichment_cache,
    )


@dataclass(slots=True)
class PipelineRuntime:
    """Runtime resources required for executing the pipeline."""

    site_paths: SitePaths
    runtime_db_uri: str
    pipeline_backend: any
    runs_backend: any
    cli_model_override: str | None
    client: genai.Client
    enrichment_cache: EnrichmentCache


@dataclass(slots=True)
class PreparedDataset:
    """Dataset artifacts prepared prior to window iteration."""

    messages_table: ir.Table
    windows_iterator: any
    checkpoint_path: Path
    window_context: WindowProcessingContext
    enable_enrichment: bool
    embedding_model: str


def _close_backend(backend: any) -> None:
    """Close an Ibis backend if it exposes a closeable interface."""
    if backend is None:
        return

    close_method = getattr(backend, "close", None)
    if callable(close_method):
        close_method()
    elif hasattr(backend, "con") and hasattr(backend.con, "close"):
        backend.con.close()


@contextmanager
def _pipeline_resources(
    output_dir: Path,
    config: EgregoraConfig,
    api_key: str | None,
    model_override: str | None,
    client: genai.Client | None,
) -> PipelineRuntime:
    """Context manager that provisions and tears down pipeline resources."""
    options = getattr(ibis, "options", None)
    previous_backend = getattr(options, "default_backend", None) if options else None

    if client is None:
        (
            site_paths,
            runtime_db_uri,
            pipeline_backend,
            runs_backend,
            cli_model_override,
            active_client,
            enrichment_cache,
        ) = _setup_pipeline_environment(output_dir, config, api_key, model_override)
    else:
        output_dir = output_dir.expanduser().resolve()
        site_paths = _resolve_site_paths_or_raise(output_dir, config)
        runtime_db_uri, pipeline_backend, runs_backend = _create_database_backends(
            site_paths.site_root, config
        )
        cli_model_override = model_override
        cache_dir = Path(".egregora-cache") / site_paths.site_root.name
        enrichment_cache = EnrichmentCache(cache_dir)
        active_client = client

    if options is not None:
        options.default_backend = pipeline_backend

    runtime = PipelineRuntime(
        site_paths=site_paths,
        runtime_db_uri=runtime_db_uri,
        pipeline_backend=pipeline_backend,
        runs_backend=runs_backend,
        cli_model_override=cli_model_override,
        client=active_client,
        enrichment_cache=enrichment_cache,
    )

    try:
        yield runtime
    finally:
        try:
            runtime.enrichment_cache.close()
        finally:
            try:
                _close_backend(runtime.runs_backend)
            finally:
                try:
                    runtime.client.close()
                finally:
                    if options is not None:
                        options.default_backend = previous_backend
                    _close_backend(runtime.pipeline_backend)


def _parse_and_validate_source(adapter: any, input_path: Path, timezone: str) -> ir.Table:
    """Parse source and validate IR schema.

    Args:
        adapter: Source adapter instance
        input_path: Path to input file
        timezone: Timezone string

    Returns:
        messages_table: Validated messages table

    Raises:
        ValueError: If IR schema validation fails

    """
    logger.info("[bold cyan]📦 Parsing with adapter:[/] %s", adapter.source_name)
    messages_table = adapter.parse(input_path, timezone=timezone)

    # Validate IR schema (raises SchemaError if invalid)
    validate_ir_schema(messages_table)

    total_messages = messages_table.count().execute()
    logger.info("[green]✅ Parsed[/] %s messages", total_messages)

    metadata = adapter.get_metadata(input_path)
    logger.info("[yellow]👥 Group:[/] %s", metadata.get("group_name", "Unknown"))

    return messages_table


def _setup_content_directories(site_paths: any) -> None:
    """Create and validate content directories.

    Args:
        site_paths: Site path configuration

    Raises:
        ValueError: If directories are not inside docs_dir

    """
    content_dirs = {
        "posts": site_paths.posts_dir,
        "profiles": site_paths.profiles_dir,
        "media": site_paths.media_dir,
    }

    for label, directory in content_dirs.items():
        if label == "media":
            try:
                directory.relative_to(site_paths.docs_dir)
            except ValueError:
                try:
                    directory.relative_to(site_paths.site_root)
                except ValueError as exc:
                    msg = (
                        "Media directory must reside inside the MkDocs docs_dir or the site root. "
                        f"Expected parent {site_paths.docs_dir} or {site_paths.site_root}, got {directory}."
                    )
                    raise ValueError(msg) from exc
            directory.mkdir(parents=True, exist_ok=True)
            continue

        try:
            directory.relative_to(site_paths.docs_dir)
        except ValueError as exc:
            msg = f"{label.capitalize()} directory must reside inside the MkDocs docs_dir. Expected parent {site_paths.docs_dir}, got {directory}."
            raise ValueError(msg) from exc
        directory.mkdir(parents=True, exist_ok=True)


def _process_commands_and_avatars(
    messages_table: ir.Table, site_paths: any, vision_model: str, enrichment_cache: EnrichmentCache
) -> ir.Table:
    """Process egregora commands and avatar commands.

    Args:
        messages_table: Input messages table
        site_paths: Site path configuration
        vision_model: Vision model identifier
        enrichment_cache: Enrichment cache instance

    Returns:
        Messages table (unchanged, commands are side effects)

    """
    commands = extract_commands(messages_table)
    if commands:
        process_commands(commands, site_paths.profiles_dir)
        logger.info("[magenta]🧾 Processed[/] %s /egregora commands", len(commands))
    else:
        logger.info("[magenta]🧾 No /egregora commands detected[/]")

    logger.info("[cyan]🖼️  Processing avatar commands...[/]")
    avatar_context = AvatarContext(
        docs_dir=site_paths.docs_dir,
        media_dir=site_paths.media_dir,
        profiles_dir=site_paths.profiles_dir,
        vision_model=vision_model,
        cache=enrichment_cache,
    )
    avatar_results = process_avatar_commands(
        messages_table=messages_table,
        context=avatar_context,
    )
    if avatar_results:
        logger.info("[green]✓ Processed[/] %s avatar command(s)", len(avatar_results))

    return messages_table


def _prepare_dataset(
    adapter: any,
    input_path: Path,
    config: EgregoraConfig,
    runtime: PipelineRuntime,
) -> PreparedDataset:
    """Prepare dataset, filters, and window context prior to iteration."""
    timezone = config.pipeline.timezone
    step_size = config.pipeline.step_size
    step_unit = config.pipeline.step_unit
    overlap_ratio = config.pipeline.overlap_ratio
    max_window_time_hours = config.pipeline.max_window_time
    max_window_time = timedelta(hours=max_window_time_hours) if max_window_time_hours else None
    enable_enrichment = config.enrichment.enabled
    retrieval_mode = config.rag.mode
    retrieval_nprobe = config.rag.nprobe
    retrieval_overfetch = config.rag.overfetch

    from_date: date_type | None = None
    to_date: date_type | None = None
    if config.pipeline.from_date:
        from_date = date_type.fromisoformat(config.pipeline.from_date)
    if config.pipeline.to_date:
        to_date = date_type.fromisoformat(config.pipeline.to_date)

    vision_model = get_model_for_task("enricher_vision", config, runtime.cli_model_override)
    embedding_model = get_model_for_task("embedding", config, runtime.cli_model_override)

    messages_table = _parse_and_validate_source(adapter, input_path, timezone)
    _setup_content_directories(runtime.site_paths)
    messages_table = _process_commands_and_avatars(
        messages_table, runtime.site_paths, vision_model, runtime.enrichment_cache
    )

    checkpoint_path = runtime.site_paths.site_root / ".egregora" / "checkpoint.json"
    messages_table = _apply_filters(messages_table, runtime.site_paths, from_date, to_date, checkpoint_path)

    from egregora.output_adapters import create_output_format

    output_format = create_output_format(runtime.site_paths.site_root, format_type=config.output.format)

    if config.rag.enabled:
        logger.info("[bold cyan]📚 Indexing existing documents into RAG...[/]")
        try:
            from egregora.agents.writer.writer_runner import index_documents_for_rag

            indexed_count = index_documents_for_rag(
                output_format, runtime.site_paths.rag_dir, embedding_model=embedding_model
            )
            if indexed_count > 0:
                logger.info("[green]✓ Indexed[/] %s documents into RAG", indexed_count)
            else:
                logger.info("[dim]No new documents to index[/]")
        except Exception:
            logger.exception("[yellow]⚠️  Failed to index documents into RAG[/]")

    window_context = WindowProcessingContext(
        adapter=adapter,
        input_path=input_path,
        site_paths=runtime.site_paths,
        posts_dir=runtime.site_paths.posts_dir,
        profiles_dir=runtime.site_paths.profiles_dir,
        config=config,
        enrichment_cache=runtime.enrichment_cache,
        output_format=output_format,
        enable_enrichment=enable_enrichment,
        cli_model_override=runtime.cli_model_override,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        client=runtime.client,
    )

    logger.info("🎯 [bold cyan]Creating windows:[/] step_size=%s, unit=%s", step_size, step_unit)

    windows_iterator = create_windows(
        messages_table,
        step_size=step_size,
        step_unit=step_unit,
        overlap_ratio=overlap_ratio,
        max_window_time=max_window_time,
    )

    return PreparedDataset(
        messages_table=messages_table,
        windows_iterator=windows_iterator,
        checkpoint_path=checkpoint_path,
        window_context=window_context,
        enable_enrichment=enable_enrichment,
        embedding_model=embedding_model,
    )


def _index_media_into_rag(
    enable_enrichment: bool,
    results: dict,
    site_paths: any,
    embedding_model: str,
) -> None:
    """Index media enrichments into RAG after window processing.

    Args:
        enable_enrichment: Whether enrichment is enabled
        results: Window processing results
        site_paths: Site path configuration
        embedding_model: Embedding model identifier

    """
    if not (enable_enrichment and results):
        return

    logger.info("[bold cyan]📚 Indexing media into RAG...[/]")
    try:
        rag_dir = site_paths.rag_dir
        store = VectorStore(rag_dir / "chunks.parquet")
        media_chunks = index_all_media(site_paths.docs_dir, store, embedding_model=embedding_model)
        if media_chunks > 0:
            logger.info("[green]✓ Indexed[/] %s media chunks into RAG", media_chunks)
        else:
            logger.info("[yellow]No media enrichments to index[/]")
    except Exception:
        logger.exception("[red]Failed to index media into RAG[/]")


def _save_checkpoint(results: dict, messages_table: ir.Table, checkpoint_path: Path) -> None:
    """Save checkpoint after successful window processing.

    Args:
        results: Window processing results
        messages_table: Filtered messages table
        checkpoint_path: Path to checkpoint file

    """
    if not results:
        logger.warning(
            "⚠️  [yellow]No windows processed[/] - checkpoint not saved. "
            "All windows may have been empty or filtered out."
        )
        return

    # Checkpoint based on messages in the filtered table
    checkpoint_stats = messages_table.aggregate(
        max_timestamp=messages_table.ts.max(),
        total_processed=messages_table.count(),
    ).execute()

    total_processed = checkpoint_stats["total_processed"][0]
    max_timestamp = checkpoint_stats["max_timestamp"][0]
    save_checkpoint(checkpoint_path, max_timestamp, total_processed)
    logger.info(
        "💾 [cyan]Checkpoint saved:[/] processed up to %s (%d posts written)",
        max_timestamp.strftime("%Y-%m-%d %H:%M:%S") if max_timestamp else "N/A",
        len(results),
    )


def _execute_windows(dataset: PreparedDataset, runtime: PipelineRuntime) -> dict[str, dict[str, list[str]]]:
    """Run window iteration, enrichment indexing, and checkpoint persistence."""
    results = _process_all_windows(dataset.windows_iterator, dataset.window_context, runtime.runs_backend)
    _index_media_into_rag(dataset.enable_enrichment, results, runtime.site_paths, dataset.embedding_model)
    _save_checkpoint(results, dataset.messages_table, dataset.checkpoint_path)
    logger.info("[bold green]🎉 Pipeline completed successfully![/]")
    return results


def _apply_filters(
    messages_table: ir.Table,
    site_paths: any,
    from_date: date_type | None,
    to_date: date_type | None,
    checkpoint_path: Path,
) -> ir.Table:
    """Apply all filters: egregora messages, opted-out users, date range, checkpoint resume.

    Args:
        messages_table: Input messages table
        site_paths: Site path configuration
        from_date: Filter start date (inclusive)
        to_date: Filter end date (inclusive)
        checkpoint_path: Path to checkpoint file

    Returns:
        Filtered messages table

    """
    # Filter egregora messages
    messages_table, egregora_removed = filter_egregora_messages(messages_table)
    if egregora_removed:
        logger.info("[yellow]🧹 Removed[/] %s /egregora messages", egregora_removed)

    # Filter opted-out authors
    messages_table, removed_count = filter_opted_out_authors(messages_table, site_paths.profiles_dir)
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

    # Checkpoint-based resume logic
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
        logger.info("🆕 [cyan]Starting fresh[/] (no checkpoint found)")

    return messages_table


def run(
    source: str,
    input_path: Path,
    output_dir: Path,
    config: EgregoraConfig,
    *,
    api_key: str | None = None,
    model_override: str | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Run the complete write pipeline workflow.

    MODERN (Phase 2): Uses EgregoraConfig instead of 16 individual parameters.

    This is the main entry point for processing chat exports from any source.
    It handles:
    1. Source adapter selection and IR parsing
    2. Command and avatar processing
    3. Filtering (egregora messages, opted-out users, date range)
    4. Window creation (flexible grouping by message count, time, or tokens)
    5. Media extraction and enrichment (optional)
    6. Post writing with LLM
    7. RAG indexing

    Args:
        source: Source identifier ("whatsapp", "slack", etc.)
        input_path: Path to input file (ZIP, JSON, etc.)
        output_dir: Output directory for generated content
        config: Egregora configuration (models, RAG, pipeline, enrichment, etc.)
        api_key: Google Gemini API key (optional override)
        model_override: Model override for CLI --model flag
        client: Optional pre-configured genai.Client

    Returns:
        Dict mapping window IDs to {'posts': [...], 'profiles': [...]}

    Raises:
        ValueError: If source is unknown or configuration is invalid
        RuntimeError: If pipeline execution fails

    """
    logger.info("[bold cyan]🚀 Starting pipeline for source:[/] %s", source)
    adapter = get_adapter(source)

    with _pipeline_resources(output_dir, config, api_key, model_override, client) as runtime:
        dataset = _prepare_dataset(adapter, input_path, config, runtime)
        return _execute_windows(dataset, runtime)
