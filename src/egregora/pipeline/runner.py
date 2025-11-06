"""High-level pipeline runner - sets up and executes the complete pipeline.

This module provides the main entry point for running the source-agnostic pipeline.
It handles the complete flow from parsing to final output generation.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import date
from pathlib import Path

import duckdb
import ibis
from google import genai

from egregora.adapters import get_adapter
from egregora.agents.tools.profiler import filter_opted_out_authors, process_commands
from egregora.agents.tools.rag import VectorStore, index_all_media
from egregora.agents.writer import write_posts_for_period
from egregora.config import ModelConfig, load_site_config, resolve_site_paths
from egregora.constants import StepStatus
from egregora.enrichment import enrich_table
from egregora.enrichment.avatar_pipeline import process_avatar_commands
from egregora.ingestion.parser import extract_commands, filter_egregora_messages
from egregora.pipeline.ir import validate_ir_schema
from egregora.pipeline.media_utils import process_media_for_period
from egregora.types import GroupSlug
from egregora.utils.cache import EnrichmentCache
from egregora.utils.checkpoints import CheckpointStore

logger = logging.getLogger(__name__)

__all__ = ["run_source_pipeline"]


def run_source_pipeline(  # noqa: PLR0913, PLR0915
    source: str,
    input_path: Path,
    output_dir: Path,
    *,
    period: str = "day",
    enable_enrichment: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
    timezone: str | None = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Run the complete source-agnostic pipeline.

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
        period: Grouping period ("day", "week", "month")
        enable_enrichment: Whether to enrich with URL/media context
        from_date: Optional start date filter
        to_date: Optional end date filter
        timezone: Timezone for timestamp normalization
        gemini_api_key: Google Gemini API key
        model: Model override
        resume: Whether to resume from checkpoints
        batch_threshold: Threshold for batch processing
        retrieval_mode: RAG retrieval mode ("ann" or "exact")
        retrieval_nprobe: Number of probes for ANN retrieval
        retrieval_overfetch: Overfetch factor for retrieval
        client: Optional pre-configured genai.Client

    Returns:
        Dict mapping period keys to {'posts': [...], 'profiles': [...]}

    Raises:
        ValueError: If source is unknown or configuration is invalid
        RuntimeError: If pipeline execution fails
    """
    # Import group_by_period from the parent module
    from egregora.pipeline import group_by_period

    def _load_enriched_table(path: Path, schema):
        if not path.exists():
            raise FileNotFoundError(path)
        return ibis.read_csv(str(path), table_schema=schema)

    # Step 1: Get source adapter
    logger.info(f"[bold cyan]🚀 Starting pipeline for source:[/] {source}")
    adapter = get_adapter(source)

    # Step 2: Resolve site paths and validate MkDocs scaffold
    output_dir = output_dir.expanduser().resolve()
    site_paths = resolve_site_paths(output_dir)

    if not site_paths.mkdocs_path or not site_paths.mkdocs_path.exists():
        raise ValueError(
            f"No mkdocs.yml found for site at {output_dir}. "
            "Run 'egregora init <site-dir>' before processing exports."
        )

    if not site_paths.docs_dir.exists():
        raise ValueError(
            f"Docs directory not found: {site_paths.docs_dir}. "
            "Re-run 'egregora init' to scaffold the MkDocs project."
        )

    # Step 3: Set up database backend
    runtime_db_path = site_paths.site_root / ".egregora" / "pipeline.duckdb"
    runtime_db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(runtime_db_path))
    backend = ibis.duckdb.from_connection(connection)

    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None

    try:
        if options is not None:
            options.default_backend = backend

        # Step 4: Load configuration
        site_config = load_site_config(site_paths.site_root)
        model_config = ModelConfig(cli_model=model, site_config=site_config)

        # Step 5: Initialize Gemini client
        if client is None:
            client = genai.Client(api_key=gemini_api_key)

        # Get model names for enrichment and embedding
        text_model = model_config.get_model("enricher")
        vision_model = model_config.get_model("enricher_vision")
        embedding_model = model_config.get_model("embedding")
        embedding_dimensionality = model_config.embedding_output_dimensionality

        cache_dir = Path(".egregora-cache") / site_paths.site_root.name
        enrichment_cache = EnrichmentCache(cache_dir)
        checkpoint_store = CheckpointStore(site_paths.site_root / ".egregora" / "checkpoints")

        # Step 6: Parse with source adapter
        logger.info(f"[bold cyan]📦 Parsing with adapter:[/] {adapter.source_name}")
        messages_table = adapter.parse(input_path, timezone=timezone)

        # Validate IR schema
        is_valid, errors = validate_ir_schema(messages_table)
        if not is_valid:
            raise ValueError(
                "Source adapter produced invalid IR schema. Errors:\n"
                + "\n".join(f"  - {err}" for err in errors)
            )

        total_messages = messages_table.count().execute()
        logger.info(f"[green]✅ Parsed[/] {total_messages} messages")

        # Step 7: Get metadata
        metadata = adapter.get_metadata(input_path)
        group_slug = GroupSlug(metadata.get("group_slug", "unknown"))
        logger.info(f"[yellow]👥 Group:[/] {metadata.get('group_name', 'Unknown')}")

        # Step 8: Ensure content directories exist
        content_dirs = {
            "posts": site_paths.posts_dir,
            "profiles": site_paths.profiles_dir,
            "media": site_paths.media_dir,
        }
        for label, directory in content_dirs.items():
            try:
                directory.relative_to(site_paths.docs_dir)
            except ValueError as exc:
                raise ValueError(
                    f"{label.capitalize()} directory must reside inside the MkDocs docs_dir. "
                    f"Expected parent {site_paths.docs_dir}, got {directory}."
                ) from exc
            directory.mkdir(parents=True, exist_ok=True)

        # Step 9: Extract and process /egregora commands
        commands = extract_commands(messages_table)
        if commands:
            process_commands(commands, site_paths.profiles_dir)
            logger.info(f"[magenta]🧾 Processed[/] {len(commands)} /egregora commands")
        else:
            logger.info("[magenta]🧾 No /egregora commands detected[/]")

        # Step 10: Process avatar commands
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
            logger.info(f"[green]✓ Processed[/] {len(avatar_results)} avatar command(s)")

        # Step 11: Filter messages
        messages_table, egregora_removed = filter_egregora_messages(messages_table)
        if egregora_removed:
            logger.info(f"[yellow]🧹 Removed[/] {egregora_removed} /egregora messages")

        messages_table, removed_count = filter_opted_out_authors(messages_table, site_paths.profiles_dir)
        if removed_count > 0:
            logger.warning(f"⚠️  {removed_count} messages removed from opted-out users")

        # Step 12: Apply date range filter
        if from_date or to_date:
            original_count = messages_table.count().execute()

            if from_date and to_date:
                messages_table = messages_table.filter(
                    (messages_table.timestamp.date() >= from_date)
                    & (messages_table.timestamp.date() <= to_date)
                )
                logger.info(f"📅 [cyan]Filtering[/] from {from_date} to {to_date}")
            elif from_date:
                messages_table = messages_table.filter(messages_table.timestamp.date() >= from_date)
                logger.info(f"📅 [cyan]Filtering[/] from {from_date} onwards")
            elif to_date:
                messages_table = messages_table.filter(messages_table.timestamp.date() <= to_date)
                logger.info(f"📅 [cyan]Filtering[/] up to {to_date}")

            filtered_count = messages_table.count().execute()
            removed_by_date = original_count - filtered_count

            if removed_by_date > 0:
                logger.info(f"🗓️  [yellow]Filtered out[/] {removed_by_date} messages (kept {filtered_count})")

        # Step 13: Group by period
        logger.info(f"🎯 [bold cyan]Grouping by period:[/] {period}")
        periods = group_by_period(messages_table, period)
        if not periods:
            logger.info("[yellow]No periods found after grouping[/]")
            return {}

        # Step 14: Process each period
        results = {}
        posts_dir = site_paths.posts_dir
        profiles_dir = site_paths.profiles_dir
        site_paths.enriched_dir.mkdir(parents=True, exist_ok=True)

        for period_key in sorted(periods.keys()):
            period_table = periods[period_key]
            period_count = period_table.count().execute()
            logger.info(f"➡️  [bold]{period_key}[/] — {period_count} messages")

            checkpoint_data = checkpoint_store.load(period_key) if resume else {"steps": {}}
            steps_state = checkpoint_data.get("steps", {})

            # Extract media for this period using new source-agnostic architecture
            # Create temp directory for media processing
            with tempfile.TemporaryDirectory(prefix=f"egregora-media-{period_key}-") as temp_dir_str:
                temp_dir = Path(temp_dir_str)

                # Process media: extract markdown refs, deliver via adapter, standardize names
                period_table, media_mapping = process_media_for_period(
                    period_table=period_table,
                    adapter=adapter,
                    media_dir=site_paths.media_dir,
                    temp_dir=temp_dir,
                    docs_dir=site_paths.docs_dir,
                    posts_dir=posts_dir,
                    zip_path=input_path,  # WhatsApp-specific kwarg
                )

            logger.info(f"Processing {period_key}...")
            enriched_path = site_paths.enriched_dir / f"{period_key}-enriched.csv"

            # Enrichment stage (optional)
            if enable_enrichment:
                logger.info(f"✨ [cyan]Enriching[/] period {period_key}")
                if resume and steps_state.get("enrichment") == StepStatus.COMPLETED.value:
                    try:
                        enriched_table = _load_enriched_table(enriched_path, period_table.schema())
                        logger.info(f"Loaded cached enrichment for {period_key}")
                    except FileNotFoundError:
                        logger.info(f"Cached enrichment missing; regenerating {period_key}")
                        if resume:
                            steps_state = checkpoint_store.update_step(
                                period_key, "enrichment", "in_progress"
                            )["steps"]
                        enriched_table = enrich_table(
                            period_table,
                            media_mapping,
                            client,
                            client,
                            enrichment_cache,
                            site_paths.docs_dir,
                            posts_dir,
                            model_config,
                        )
                        enriched_table.execute().to_csv(enriched_path, index=False)
                        if resume:
                            steps_state = checkpoint_store.update_step(period_key, "enrichment", "completed")[
                                "steps"
                            ]
                else:
                    if resume:
                        steps_state = checkpoint_store.update_step(period_key, "enrichment", "in_progress")[
                            "steps"
                        ]
                    enriched_table = enrich_table(
                        period_table,
                        media_mapping,
                        client,
                        client,
                        enrichment_cache,
                        site_paths.docs_dir,
                        posts_dir,
                        model_config,
                    )
                    enriched_table.execute().to_csv(enriched_path, index=False)
                    if resume:
                        steps_state = checkpoint_store.update_step(period_key, "enrichment", "completed")[
                            "steps"
                        ]
            else:
                enriched_table = period_table
                enriched_table.execute().to_csv(enriched_path, index=False)

            # Writing stage
            if resume and steps_state.get("writing") == StepStatus.COMPLETED.value:
                logger.info(f"Resuming posts for {period_key} from existing files")
                existing_posts = sorted(posts_dir.glob(f"{period_key}-*.md"))
                result = {
                    "posts": [str(p) for p in existing_posts],
                    "profiles": [],
                }
            else:
                if resume:
                    steps_state = checkpoint_store.update_step(period_key, "writing", "in_progress")["steps"]

                # Import WriterConfig here to avoid circular imports
                from egregora.agents.writer import WriterConfig

                writer_config = WriterConfig(
                    output_dir=posts_dir,
                    profiles_dir=profiles_dir,
                    rag_dir=site_paths.rag_dir,
                    model_config=model_config,
                    enable_rag=True,
                    embedding_output_dimensionality=embedding_dimensionality,
                    retrieval_mode=retrieval_mode,
                    retrieval_nprobe=retrieval_nprobe,
                    retrieval_overfetch=retrieval_overfetch,
                )

                result = write_posts_for_period(
                    enriched_table,
                    period_key,
                    client,
                    writer_config,
                )
                if resume:
                    steps_state = checkpoint_store.update_step(period_key, "writing", "completed")["steps"]

            results[period_key] = result
            post_count = len(result.get("posts", []))
            profile_count = len(result.get("profiles", []))
            logger.info(
                f"[green]✔ Generated[/] {post_count} posts / {profile_count} profiles for {period_key}"
            )

        # Step 15: Index media into RAG
        if enable_enrichment and results:
            logger.info("[bold cyan]📚 Indexing media into RAG...[/]")
            try:
                rag_dir = site_paths.rag_dir
                store = VectorStore(rag_dir / "chunks.parquet")
                media_chunks = index_all_media(
                    site_paths.docs_dir,
                    store,
                    embedding_model=embedding_model,
                    output_dimensionality=embedding_dimensionality,
                )
                if media_chunks > 0:
                    logger.info(f"[green]✓ Indexed[/] {media_chunks} media chunks into RAG")
                else:
                    logger.info("[yellow]No media enrichments to index[/]")
            except Exception as e:
                logger.error(f"[red]Failed to index media into RAG:[/] {e}")

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
