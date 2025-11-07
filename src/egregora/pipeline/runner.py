"""High-level pipeline runner - sets up and executes the complete pipeline.

This module provides the main entry point for running the source-agnostic pipeline.
It handles the complete flow from parsing to final output generation.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import date as date_type
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import duckdb
import ibis
from google import genai

from egregora.adapters import get_adapter
from egregora.agents.tools.profiler import filter_opted_out_authors, process_commands
from egregora.agents.tools.rag import VectorStore, index_all_media
from egregora.agents.writer import WriterConfig, write_posts_for_window
from egregora.config import ModelConfig, resolve_site_paths
from egregora.config.schema import EgregoraConfig
from egregora.enrichment import enrich_table
from egregora.enrichment.avatar_pipeline import process_avatar_commands
from egregora.enrichment.core import EnrichmentRuntimeContext
from egregora.ingestion import extract_commands, filter_egregora_messages  # Phase 6: Re-exported
from egregora.pipeline import create_windows, load_checkpoint, save_checkpoint
from egregora.pipeline.ir import validate_ir_schema
from egregora.pipeline.media_utils import process_media_for_window
from egregora.types import GroupSlug
from egregora.utils.cache import EnrichmentCache

if TYPE_CHECKING:
    import ibis.expr.types as ir
logger = logging.getLogger(__name__)
__all__ = ["run_source_pipeline"]


def _perform_enrichment(  # noqa: PLR0913
    window_table: ir.Table,
    media_mapping: dict[str, Path],
    config: EgregoraConfig,
    enrichment_cache: EnrichmentCache,
    site_paths: any,
    posts_dir: Path,
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

    Returns:
        Enriched table

    """
    enrichment_context = EnrichmentRuntimeContext(
        cache=enrichment_cache,
        docs_dir=site_paths.docs_dir,
        posts_dir=posts_dir,
    )
    return enrich_table(
        window_table,
        media_mapping,
        config,
        enrichment_context,
    )


def run_source_pipeline(  # noqa: PLR0913, PLR0912, PLR0915, C901
    source: str,
    input_path: Path,
    output_dir: Path,
    config: EgregoraConfig,
    *,
    api_key: str | None = None,
    model_override: str | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Run the complete source-agnostic pipeline.

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
    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None
    try:
        if options is not None:
            options.default_backend = backend
        # Extract config values (Phase 2: reduced from 16 params to EgregoraConfig)
        timezone = config.pipeline.timezone
        step_size = config.pipeline.step_size
        step_unit = config.pipeline.step_unit
        min_window_size = config.pipeline.min_window_size
        overlap_ratio = config.pipeline.overlap_ratio
        max_window_time_hours = config.pipeline.max_window_time
        # Convert hours to timedelta if specified (schema stores as int, pipeline expects timedelta)
        max_window_time = timedelta(hours=max_window_time_hours) if max_window_time_hours else None
        batch_threshold = config.pipeline.batch_threshold
        enable_enrichment = config.enrichment.enabled
        retrieval_mode = config.rag.mode
        retrieval_nprobe = config.rag.nprobe
        retrieval_overfetch = config.rag.overfetch

        # Parse date strings if provided
        from_date: date_type | None = None
        to_date: date_type | None = None
        if config.pipeline.from_date:
            from_date = date_type.fromisoformat(config.pipeline.from_date)
        if config.pipeline.to_date:
            to_date = date_type.fromisoformat(config.pipeline.to_date)

        model_config = ModelConfig(config=config, cli_model=model_override)
        if client is None:
            client = genai.Client(api_key=api_key)
        text_model = model_config.get_model("enricher")
        vision_model = model_config.get_model("enricher_vision")
        embedding_model = model_config.get_model("embedding")
        cache_dir = Path(".egregora-cache") / site_paths.site_root.name
        enrichment_cache = EnrichmentCache(cache_dir)
        logger.info("[bold cyan]📦 Parsing with adapter:[/] %s", adapter.source_name)
        messages_table = adapter.parse(input_path, timezone=timezone)
        is_valid, errors = validate_ir_schema(messages_table)
        if not is_valid:
            raise ValueError(
                "Source adapter produced invalid IR schema. Errors:\n"
                + "\n".join(f"  - {err}" for err in errors)
            )
        total_messages = messages_table.count().execute()
        logger.info("[green]✅ Parsed[/] %s messages", total_messages)
        metadata = adapter.get_metadata(input_path)
        group_slug = GroupSlug(metadata.get("group_slug", "unknown"))
        logger.info("[yellow]👥 Group:[/] %s", metadata.get("group_name", "Unknown"))
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
        commands = extract_commands(messages_table)
        if commands:
            process_commands(commands, site_paths.profiles_dir)
            logger.info("[magenta]🧾 Processed[/] %s /egregora commands", len(commands))
        else:
            logger.info("[magenta]🧾 No /egregora commands detected[/]")
        logger.info("[cyan]🖼️  Processing avatar commands...[/]")
        avatar_results = process_avatar_commands(
            messages_table=messages_table,
            zip_path=input_path,
            docs_dir=site_paths.docs_dir,
            profiles_dir=site_paths.profiles_dir,
            group_slug=str(group_slug),
            vision_client=client,
            model=vision_model,
        )
        if avatar_results:
            logger.info("[green]✓ Processed[/] %s avatar command(s)", len(avatar_results))
        messages_table, egregora_removed = filter_egregora_messages(messages_table)
        if egregora_removed:
            logger.info("[yellow]🧹 Removed[/] %s /egregora messages", egregora_removed)
        messages_table, removed_count = filter_opted_out_authors(messages_table, site_paths.profiles_dir)
        if removed_count > 0:
            logger.warning("⚠️  %s messages removed from opted-out users", removed_count)
        if from_date or to_date:
            original_count = messages_table.count().execute()
            if from_date and to_date:
                messages_table = messages_table.filter(
                    (messages_table.timestamp.date() >= from_date)
                    & (messages_table.timestamp.date() <= to_date)
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
                logger.info(
                    "🗓️  [yellow]Filtered out[/] %s messages (kept %s)", removed_by_date, filtered_count
                )

        # Phase 7: Checkpoint-based resume logic
        checkpoint_path = site_paths.site_root / ".egregora" / "checkpoint.json"
        checkpoint = load_checkpoint(checkpoint_path)
        if checkpoint and "last_processed_timestamp" in checkpoint:
            last_timestamp_str = checkpoint["last_processed_timestamp"]
            last_timestamp = datetime.fromisoformat(last_timestamp_str)

            # Ensure timezone-aware comparison
            if last_timestamp.tzinfo is None:
                last_timestamp = last_timestamp.replace(tzinfo=ZoneInfo("UTC"))

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

        logger.info("🎯 [bold cyan]Creating windows:[/] step_size=%s, unit=%s", step_size, step_unit)
        windows_iterator = create_windows(
            messages_table,
            step_size=step_size,
            step_unit=step_unit,
            min_window_size=min_window_size,
            overlap_ratio=overlap_ratio,
            max_window_time=max_window_time,
        )

        results = {}
        posts_dir = site_paths.posts_dir
        profiles_dir = site_paths.profiles_dir

        def process_window_with_auto_split(
            window: Window,  # noqa: F821
            *,
            depth: int = 0,
            max_depth: int = 5,
        ) -> dict[str, dict[str, list[str]]]:
            """Process a window with automatic splitting if prompt exceeds model limit.

            Args:
                window: Window to process
                depth: Current recursion depth (for logging)
                max_depth: Maximum recursion depth to prevent infinite splitting

            Returns:
                Dict mapping window_id to {'posts': [...], 'profiles': [...]}

            Raises:
                RuntimeError: If max recursion depth reached

            """
            from egregora.agents.model_limits import PromptTooLargeError  # noqa: PLC0415
            from egregora.pipeline import split_window_in_half  # noqa: PLC0415

            # Constants
            min_window_size = 5  # Minimum messages before we stop splitting

            indent = "  " * depth
            window_id = window.window_id
            window_table = window.table
            window_count = window.size

            logger.info("%s➡️  [bold]%s[/] — %s messages (depth=%d)", indent, window_id, window_count, depth)

            # Stop splitting if window too small or max depth reached
            if window_count < min_window_size:
                logger.warning(
                    "%s⚠️  Window %s too small to split (%d messages) - attempting anyway",
                    indent,
                    window_id,
                    window_count,
                )
            if depth >= max_depth:
                error_msg = (
                    f"Max recursion depth {max_depth} reached for window {window_id}. "
                    "Window cannot be split small enough to fit in model context. "
                    "Try increasing --max-prompt-tokens or using --use-full-context-window."
                )
                logger.error("%s❌ %s", indent, error_msg)
                raise RuntimeError(error_msg)

            try:
                # Try to process the window normally
                with tempfile.TemporaryDirectory(prefix=f"egregora-media-{window_id}-") as temp_dir_str:
                    temp_dir = Path(temp_dir_str)
                    window_table_processed, media_mapping = process_media_for_window(
                        window_table=window_table,
                        adapter=adapter,
                        media_dir=site_paths.media_dir,
                        temp_dir=temp_dir,
                        docs_dir=site_paths.docs_dir,
                        posts_dir=posts_dir,
                        zip_path=input_path,
                    )

                if enable_enrichment:
                    logger.info("%s✨ [cyan]Enriching[/] window %s", indent, window_id)
                    enriched_table = _perform_enrichment(
                        window_table_processed, media_mapping, config, enrichment_cache, site_paths, posts_dir
                    )
                else:
                    enriched_table = window_table_processed

                writer_config = WriterConfig(
                    output_dir=posts_dir,
                    profiles_dir=profiles_dir,
                    rag_dir=site_paths.rag_dir,
                    model_config=model_config,
                    enable_rag=True,
                    retrieval_mode=retrieval_mode,
                    retrieval_nprobe=retrieval_nprobe,
                    retrieval_overfetch=retrieval_overfetch,
                )

                result = write_posts_for_window(enriched_table, window_id, client, writer_config)
                post_count = len(result.get("posts", []))
                profile_count = len(result.get("profiles", []))
                logger.info(
                    "%s[green]✔ Generated[/] %s posts / %s profiles for %s",
                    indent,
                    post_count,
                    profile_count,
                    window_id,
                )

            except PromptTooLargeError as e:
                # Prompt too large - split window and retry
                logger.warning(
                    "%s⚡ [yellow]Splitting window[/] %s (prompt: %dk tokens > %dk limit)",
                    indent,
                    window_id,
                    e.estimated_tokens // 1000,
                    e.effective_limit // 1000,
                )

                first_half, second_half = split_window_in_half(window)

                if first_half is None and second_half is None:
                    error_msg = f"Cannot split window {window_id} - both halves would be empty"
                    logger.exception("%s❌ %s", indent, error_msg)
                    raise RuntimeError(error_msg) from e

                # Recursively process each half
                combined_results = {}
                if first_half:
                    logger.info("%s↳ [dim]Processing first half[/]", indent)
                    first_results = process_window_with_auto_split(
                        first_half, depth=depth + 1, max_depth=max_depth
                    )
                    combined_results.update(first_results)

                if second_half:
                    logger.info("%s↳ [dim]Processing second half[/]", indent)
                    second_results = process_window_with_auto_split(
                        second_half, depth=depth + 1, max_depth=max_depth
                    )
                    combined_results.update(second_results)

                return combined_results
            else:
                return {window_id: result}

        # Phase 8: Process windows with automatic splitting for oversized prompts
        for window in windows_iterator:
            window_results = process_window_with_auto_split(window, depth=0, max_depth=5)
            results.update(window_results)
        if enable_enrichment and results:
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

        # Phase 7: Save checkpoint after successful processing
        if results and messages_table.count().execute() > 0:
            max_timestamp = messages_table.timestamp.max().execute()
            total_processed = messages_table.count().execute()
            save_checkpoint(checkpoint_path, max_timestamp, total_processed)
            logger.info(
                "💾 [cyan]Checkpoint saved:[/] processed up to %s",
                max_timestamp.strftime("%Y-%m-%d %H:%M:%S") if max_timestamp else "N/A",
            )

        logger.info("[bold green]🎉 Pipeline completed successfully![/]")
        return results
    finally:
        try:
            if "enrichment_cache" in locals():
                enrichment_cache.close()
        finally:
            if client:
                client.close()
        if options is not None:
            options.default_backend = old_backend
        connection.close()
