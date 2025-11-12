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
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import duckdb
import ibis
from google import genai

from egregora.agents.shared.author_profiles import filter_opted_out_authors, process_commands
from egregora.agents.shared.rag import VectorStore, index_all_media
from egregora.agents.writer import WriterConfig, write_posts_for_window
from egregora.config import get_model_for_task
from egregora.config.settings import EgregoraConfig
from egregora.database.tracking import fingerprint_window, record_run
from egregora.database.validation import validate_ir_schema
from egregora.enrichment import enrich_table
from egregora.enrichment.avatar_pipeline import AvatarContext, process_avatar_commands
from egregora.enrichment.core import EnrichmentRuntimeContext
from egregora.input_adapters import get_adapter
from egregora.output_adapters.mkdocs_site import resolve_site_paths
from egregora.sources.whatsapp.parser import extract_commands, filter_egregora_messages
from egregora.transformations import create_windows, load_checkpoint, save_checkpoint
from egregora.transformations.media import process_media_for_window
from egregora.utils.cache import EnrichmentCache

if TYPE_CHECKING:
    import ibis.expr.types as ir
logger = logging.getLogger(__name__)
__all__ = ["run"]


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


def _process_window_with_auto_split(
    window: any, ctx: WindowProcessingContext, *, depth: int = 0, max_depth: int = 5
) -> dict[str, dict[str, list[str]]]:
    """Process a window with automatic splitting if prompt exceeds model limit.

    Uses calculated upfront splitting (not recursive trial-and-error).
    Depth tracking is a safety mechanism for rare edge cases.

    Args:
        window: Window to process
        ctx: Window processing context
        depth: Current split depth (for logging and safety checks)
        max_depth: Maximum split depth to prevent pathological cases

    Returns:
        Dict mapping window labels to {'posts': [...], 'profiles': [...]}

    Raises:
        RuntimeError: If max split depth reached (indicates miscalculation)

    """
    from egregora.agents.model_limits import PromptTooLargeError
    from egregora.transformations import split_window_into_n_parts

    # Constants
    min_window_size = 5  # Minimum messages before we stop splitting

    indent = "  " * depth
    window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
    window_count = window.size

    # Stop splitting if window too small or max depth reached
    if window_count < min_window_size:
        logger.warning(
            "%s⚠️  Window %s too small to split (%d messages) - attempting anyway",
            indent,
            window_label,
            window_count,
        )
    if depth >= max_depth:
        error_msg = (
            f"Max split depth {max_depth} reached for window {window_label}. "
            "Window cannot be split enough to fit in model context (possible miscalculation). "
            "Try increasing --max-prompt-tokens or using --use-full-context-window."
        )
        logger.error("%s❌ %s", indent, error_msg)
        raise RuntimeError(error_msg)

    try:
        # Try to process the window normally
        return _process_single_window(window, ctx, depth=depth)

    except PromptTooLargeError as e:
        # Prompt too large - split window and retry
        logger.warning(
            "%s⚡ [yellow]Splitting window[/] %s (prompt: %dk tokens > %dk limit)",
            indent,
            window_label,
            e.estimated_tokens // 1000,
            e.effective_limit // 1000,
        )

        # Calculate how many splits we need upfront (deterministic, not iterative)
        import math

        num_splits = math.ceil(e.estimated_tokens / e.effective_limit)
        logger.info("%s↳ [dim]Splitting into %d parts[/]", indent, num_splits)

        split_windows = split_window_into_n_parts(window, num_splits)

        if not split_windows:
            error_msg = f"Cannot split window {window_label} - all splits would be empty"
            logger.exception("%s❌ %s", indent, error_msg)
            raise RuntimeError(error_msg) from e

        # Process each split window
        combined_results = {}
        for i, split_window in enumerate(split_windows, 1):
            split_label = f"{split_window.start_time:%Y-%m-%d %H:%M} to {split_window.end_time:%H:%M}"
            logger.info("%s↳ [dim]Processing part %d/%d: %s[/]", indent, i, len(split_windows), split_label)
            split_results = _process_window_with_auto_split(
                split_window, ctx, depth=depth + 1, max_depth=max_depth
            )
            combined_results.update(split_results)

        return combined_results


def _process_all_windows(
    windows_iterator: any, ctx: WindowProcessingContext, runs_conn: duckdb.DuckDBPyConnection
) -> dict[str, dict[str, list[str]]]:
    """Process all windows with tracking and error handling.

    Args:
        windows_iterator: Iterator of Window objects
        ctx: Window processing context
        runs_conn: DuckDB connection for run tracking

    Returns:
        Dict mapping window labels to {'posts': [...], 'profiles': [...]}

    """
    results = {}

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

        # Track window processing
        run_id = uuid.uuid4()
        started_at = datetime.now(UTC)

        # Record run start
        try:
            input_fingerprint = fingerprint_window(window)

            record_run(
                conn=runs_conn,
                run_id=run_id,
                stage=f"window_{window.window_index}",
                status="running",
                started_at=started_at,
                rows_in=window.size,
                input_fingerprint=input_fingerprint,
                trace_id=None,
            )
        except Exception as e:
            logger.warning("Failed to record run start: %s", e)

        # Process window
        try:
            window_results = _process_window_with_auto_split(window, ctx, depth=0, max_depth=5)
            results.update(window_results)

            # Record run completion
            finished_at = datetime.now(UTC)
            posts_count = sum(len(r.get("posts", [])) for r in window_results.values())
            profiles_count = sum(len(r.get("profiles", [])) for r in window_results.values())

            try:
                runs_conn.execute(
                    """
                    UPDATE runs
                    SET status = 'completed',
                        finished_at = ?,
                        duration_seconds = ?
                    WHERE run_id = ?
                    """,
                    [finished_at, (finished_at - started_at).total_seconds(), str(run_id)],
                )
                logger.debug(
                    "📊 Tracked run %s: %s posts, %s profiles",
                    str(run_id)[:8],
                    posts_count,
                    profiles_count,
                )
            except Exception as e:
                logger.warning("Failed to record run completion: %s", e)

        except Exception as e:
            # Record run failure
            finished_at = datetime.now(UTC)
            error_msg = f"{type(e).__name__}: {e!s}"

            try:
                runs_conn.execute(
                    """
                    UPDATE runs
                    SET status = 'failed',
                        finished_at = ?,
                        duration_seconds = ?,
                        error = ?
                    WHERE run_id = ?
                    """,
                    [finished_at, (finished_at - started_at).total_seconds(), error_msg, str(run_id)],
                )
            except Exception as update_err:
                logger.warning("Failed to record run failure: %s", update_err)

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


def _setup_pipeline_environment(
    output_dir: Path, config: EgregoraConfig, api_key: str | None, model_override: str | None
) -> tuple[
    any,
    Path,
    duckdb.DuckDBPyConnection,
    duckdb.DuckDBPyConnection,
    any,
    str | None,
    genai.Client,
    EnrichmentCache,
]:
    """Set up pipeline environment including paths, connections, and clients.

    Args:
        output_dir: Output directory for generated content
        config: Egregora configuration
        api_key: Google Gemini API key (optional override)
        model_override: Model override for CLI --model flag

    Returns:
        Tuple of (site_paths, runtime_db_path, connection, runs_conn, backend, model_override, client, enrichment_cache)

    Raises:
        ValueError: If mkdocs.yml or docs directory not found

    """
    output_dir = output_dir.expanduser().resolve()
    site_paths = resolve_site_paths(output_dir)

    if not site_paths.mkdocs_path or not site_paths.mkdocs_path.exists():
        msg = f"No mkdocs.yml found for site at {output_dir}. Run 'egregora init <site-dir>' before processing exports."
        raise ValueError(msg)

    if not site_paths.docs_dir.exists():
        msg = f"Docs directory not found: {site_paths.docs_dir}. Re-run 'egregora init' to scaffold the MkDocs project."
        raise ValueError(msg)

    # Setup database connections
    runtime_db_path = site_paths.site_root / ".egregora" / "pipeline.duckdb"
    runtime_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(runtime_db_path))
    backend = ibis.duckdb.from_connection(connection)

    # Setup runs tracking database
    runs_db_path = site_paths.site_root / ".egregora" / "runs.duckdb"
    runs_conn = duckdb.connect(str(runs_db_path))

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
        runtime_db_path,
        connection,
        runs_conn,
        backend,
        model_override,
        client,
        enrichment_cache,
    )


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
        max_timestamp=messages_table.timestamp.max(),
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
                (messages_table.timestamp.date() >= from_date) & (messages_table.timestamp.date() <= to_date)
            )
            logger.info("📅 [cyan]Filtering[/] from %s to %s", from_date, to_date)
        elif from_date:
            messages_table = messages_table.filter(messages_table.timestamp.date() >= from_date)
            logger.info("📅 [cyan]Filtering[/] from %s onwards", from_date)
        elif to_date:
            messages_table = messages_table.filter(messages_table.timestamp.date() <= to_date)
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
        messages_table = messages_table.filter(messages_table.timestamp > last_timestamp)
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

    # Setup environment (paths, connections, clients)
    if client is None:
        (
            site_paths,
            runtime_db_path,
            connection,
            runs_conn,
            backend,
            cli_model_override,
            client,
            enrichment_cache,
        ) = _setup_pipeline_environment(output_dir, config, api_key, model_override)
    else:
        # If client is provided, still need to setup most things
        output_dir = output_dir.expanduser().resolve()
        site_paths = resolve_site_paths(output_dir)
        if not site_paths.mkdocs_path or not site_paths.mkdocs_path.exists():
            msg = f"No mkdocs.yml found for site at {output_dir}. Run 'egregora init <site-dir>' before processing exports."
            raise ValueError(msg)
        if not site_paths.docs_dir.exists():
            msg = f"Docs directory not found: {site_paths.docs_dir}. Re-run 'egregora init' to scaffold the MkDocs project."
            raise ValueError(msg)
        runtime_db_path = site_paths.site_root / ".egregora" / "pipeline.duckdb"
        runtime_db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(runtime_db_path))
        backend = ibis.duckdb.from_connection(connection)
        runs_db_path = site_paths.site_root / ".egregora" / "runs.duckdb"
        runs_conn = duckdb.connect(str(runs_db_path))
        cli_model_override = model_override
        cache_dir = Path(".egregora-cache") / site_paths.site_root.name
        enrichment_cache = EnrichmentCache(cache_dir)

    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None
    try:
        if options is not None:
            options.default_backend = backend

        # Extract config values
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

        # Parse date filters
        from_date: date_type | None = None
        to_date: date_type | None = None
        if config.pipeline.from_date:
            from_date = date_type.fromisoformat(config.pipeline.from_date)
        if config.pipeline.to_date:
            to_date = date_type.fromisoformat(config.pipeline.to_date)

        # Get model identifiers
        vision_model = get_model_for_task("enricher_vision", config, cli_model_override)
        embedding_model = get_model_for_task("embedding", config, cli_model_override)

        # Parse and validate source
        messages_table = _parse_and_validate_source(adapter, input_path, timezone)

        # Setup content directories
        _setup_content_directories(site_paths)

        # Process commands and avatars
        messages_table = _process_commands_and_avatars(
            messages_table, site_paths, vision_model, enrichment_cache
        )

        # Apply all filters
        checkpoint_path = site_paths.site_root / ".egregora" / "checkpoint.json"
        messages_table = _apply_filters(messages_table, site_paths, from_date, to_date, checkpoint_path)

        logger.info("🎯 [bold cyan]Creating windows:[/] step_size=%s, unit=%s", step_size, step_unit)
        windows_iterator = create_windows(
            messages_table,
            step_size=step_size,
            step_unit=step_unit,
            overlap_ratio=overlap_ratio,
            max_window_time=max_window_time,
        )

        posts_dir = site_paths.posts_dir
        profiles_dir = site_paths.profiles_dir

        # Create OutputAdapter for RAG indexing (storage-agnostic)
        from egregora.output_adapters import create_output_format

        format_type = config.output.format
        output_format = create_output_format(output_dir, format_type=format_type)

        # Phase 7.5: Index all existing documents for RAG before window processing
        # This ensures the writer agent has full context from previous runs
        # Uses OutputAdapter.list_documents() - no filesystem assumptions
        if config.rag.enabled:
            logger.info("[bold cyan]📚 Indexing existing documents into RAG...[/]")
            try:
                from egregora.agents.writer.writer_runner import index_documents_for_rag

                indexed_count = index_documents_for_rag(
                    output_format, site_paths.rag_dir, embedding_model=embedding_model
                )
                if indexed_count > 0:
                    logger.info("[green]✓ Indexed[/] %s documents into RAG", indexed_count)
                else:
                    logger.info("[dim]No new documents to index[/]")
            except Exception:
                # RAG indexing failure should not block pipeline
                logger.exception("[yellow]⚠️  Failed to index documents into RAG[/]")

        # Create window processing context
        window_ctx = WindowProcessingContext(
            adapter=adapter,
            input_path=input_path,
            site_paths=site_paths,
            posts_dir=posts_dir,
            profiles_dir=profiles_dir,
            config=config,
            enrichment_cache=enrichment_cache,
            output_format=output_format,
            enable_enrichment=enable_enrichment,
            cli_model_override=cli_model_override,
            retrieval_mode=retrieval_mode,
            retrieval_nprobe=retrieval_nprobe,
            retrieval_overfetch=retrieval_overfetch,
            client=client,
        )

        # Process all windows with tracking
        results = _process_all_windows(windows_iterator, window_ctx, runs_conn)

        # Index media enrichments into RAG
        _index_media_into_rag(enable_enrichment, results, site_paths, embedding_model)

        # Save checkpoint after successful processing
        _save_checkpoint(results, messages_table, checkpoint_path)

        logger.info("[bold green]🎉 Pipeline completed successfully![/]")
        return results
    finally:
        try:
            if "enrichment_cache" in locals():
                enrichment_cache.close()
        finally:
            try:
                if "runs_conn" in locals():
                    runs_conn.close()
            finally:
                if client:
                    client.close()
        if options is not None:
            options.default_backend = old_backend
        connection.close()
