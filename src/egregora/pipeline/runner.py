"""High-level pipeline runner - sets up and executes the complete pipeline.

This module provides the main entry point for running the source-agnostic pipeline.
It handles the complete flow from parsing to final output generation.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import ibis
from google import genai

from egregora.adapters import get_adapter
from egregora.agents.tools.profiler import filter_opted_out_authors, process_commands
from egregora.agents.tools.rag import VectorStore, index_all_media
from egregora.agents.writer import write_posts_for_period
from egregora.config import ModelConfig, resolve_site_paths
from egregora.config.schema import EgregoraConfig
from egregora.enrichment import enrich_table
from egregora.enrichment.avatar_pipeline import process_avatar_commands
from egregora.enrichment.core import EnrichmentRuntimeContext
from egregora.ingestion.parser import extract_commands, filter_egregora_messages
from egregora.pipeline.ir import validate_ir_schema
from egregora.pipeline.media_utils import process_media_for_period
from egregora.types import GroupSlug
from egregora.utils.cache import EnrichmentCache

if TYPE_CHECKING:
    import ibis.expr.types as ir
logger = logging.getLogger(__name__)
__all__ = ["run_source_pipeline"]


def _perform_enrichment(
    period_table: ir.Table,
    media_mapping: dict[str, Path],
    config: EgregoraConfig,
    enrichment_cache: EnrichmentCache,
    site_paths: any,
    posts_dir: Path,
) -> ir.Table:
    """Execute enrichment for a period's table.

    Phase 3: Extracted to eliminate duplication in resume/non-resume branches.

    Args:
        period_table: Table to enrich
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
        period_table,
        media_mapping,
        config,
        enrichment_context,
    )


def run_source_pipeline(
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
    4. Period grouping
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
        Dict mapping period keys to {'posts': [...], 'profiles': [...]}

    Raises:
        ValueError: If source is unknown or configuration is invalid
        RuntimeError: If pipeline execution fails

    """
    from egregora.pipeline import group_by_period

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
        period = config.pipeline.period
        batch_threshold = config.pipeline.batch_threshold
        enable_enrichment = config.enrichment.enabled
        retrieval_mode = config.rag.mode
        retrieval_nprobe = config.rag.nprobe
        retrieval_overfetch = config.rag.overfetch

        # Parse date strings if provided
        from datetime import date as date_type

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
        logger.info("🎯 [bold cyan]Grouping by period:[/] %s", period)
        periods = group_by_period(messages_table, period)
        if not periods:
            logger.info("[yellow]No periods found after grouping[/]")
            return {}
        results = {}
        posts_dir = site_paths.posts_dir
        profiles_dir = site_paths.profiles_dir
        for period_key in sorted(periods.keys()):
            period_table = periods[period_key]
            period_count = period_table.count().execute()
            logger.info("➡️  [bold]%s[/] — %s messages", period_key, period_count)

            # Phase 3: Simple skip logic - check if posts already exist for this period
            existing_posts = sorted(posts_dir.glob(f"{period_key}-*.md"))
            if existing_posts:
                logger.info("⏭️  Skipping %s — %s existing posts found", period_key, len(existing_posts))
                result = {"posts": [str(p) for p in existing_posts], "profiles": []}
                results[period_key] = result
                continue
            with tempfile.TemporaryDirectory(prefix=f"egregora-media-{period_key}-") as temp_dir_str:
                temp_dir = Path(temp_dir_str)
                period_table, media_mapping = process_media_for_period(
                    period_table=period_table,
                    adapter=adapter,
                    media_dir=site_paths.media_dir,
                    temp_dir=temp_dir,
                    docs_dir=site_paths.docs_dir,
                    posts_dir=posts_dir,
                    zip_path=input_path,
                )
            # Phase 3: Simplified enrichment - no complex checkpointing
            if enable_enrichment:
                logger.info("✨ [cyan]Enriching[/] period %s", period_key)
                enriched_table = _perform_enrichment(
                    period_table, media_mapping, config, enrichment_cache, site_paths, posts_dir
                )
            else:
                enriched_table = period_table

            # Phase 3: Simplified writing - no checkpointing (already checked for existing posts)
            from egregora.agents.writer import WriterConfig

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
            result = write_posts_for_period(enriched_table, period_key, client, writer_config)
            results[period_key] = result
            post_count = len(result.get("posts", []))
            profile_count = len(result.get("profiles", []))
            logger.info(
                "[green]✔ Generated[/] %s posts / %s profiles for %s", post_count, profile_count, period_key
            )
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
            except Exception as e:
                logger.exception("[red]Failed to index media into RAG:[/] %s", e)
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
