"""WhatsApp-specific pipeline functions."""

import logging
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import ibis
from google import genai

from egregora.agents.tools.profiler import filter_opted_out_authors, process_commands
from egregora.agents.tools.rag import VectorStore, index_all_media
from egregora.agents.writer import WriterConfig, write_posts_for_period
from egregora.config import ModelConfig, SitePaths, load_site_config, resolve_site_paths
from egregora.constants import StepStatus
from egregora.enrichment import enrich_table, extract_and_replace_media
from egregora.enrichment.avatar_pipeline import process_avatar_commands
from egregora.ingestion.parser import extract_commands, filter_egregora_messages, parse_export
from egregora.sources.whatsapp.models import WhatsAppExport
from egregora.types import GroupSlug
from egregora.utils.cache import EnrichmentCache
from egregora.utils.checkpoints import CheckpointStore

logger = logging.getLogger(__name__)


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP and extract group name."""
    with zipfile.ZipFile(zip_path) as zf:
        candidates = []
        for member in zf.namelist():
            if member.endswith(".txt") and (not member.startswith("__")):
                pattern = "WhatsApp(?: Chat with|.*) (.+)\\.txt"
                match = re.match(pattern, Path(member).name)
                file_info = zf.getinfo(member)
                score = file_info.file_size
                if match:
                    score += 1000000
                    group_name = match.group(1)
                else:
                    group_name = Path(member).stem
                candidates.append((score, group_name, member))
        if not candidates:
            msg = f"No WhatsApp chat file found in {zip_path}"
            raise ValueError(msg)
        candidates.sort(reverse=True, key=lambda x: x[0])
        _, group_name, member = candidates[0]
        return (group_name, member)


def _process_whatsapp_export(
    zip_path: Path,
    output_dir: Path,
    *,
    site_paths: SitePaths,
    period: str = "day",
    enable_enrichment: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
    timezone: str | ZoneInfo | None = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Complete pipeline: ZIP → posts + profiles.

    Args:
        zip_path: WhatsApp export ZIP file
        output_dir: Where to save posts and profiles
        period: "day", "week", or "month"
        enable_enrichment: Add URL/media context
        from_date: Only process messages from this date onwards (date object)
        to_date: Only process messages up to this date (date object)
        timezone: ZoneInfo timezone object (WhatsApp export phone timezone)
        gemini_api_key: Google Gemini API key
        model: Gemini model to use (overrides mkdocs.yml config)
        batch_threshold: The threshold for switching to batch processing.

    Returns:
        Dict mapping period to {'posts': [...], 'profiles': [...]}

    """
    from ibis.expr.types import Schema, Table

    from egregora.pipeline import group_by_period

    def _load_enriched_table(path: Path, schema: Schema) -> Table:
        if not path.exists():
            raise FileNotFoundError(path)
        return ibis.read_csv(str(path), table_schema=schema)

    if not site_paths.mkdocs_path or not site_paths.mkdocs_path.exists():
        msg = f"No mkdocs.yml found for site at {output_dir}. Run 'egregora init <site-dir>' before processing exports."
        raise ValueError(msg)
    if not site_paths.docs_dir.exists():
        msg = f"Docs directory not found: {site_paths.docs_dir}. Re-run 'egregora init' to scaffold the MkDocs project."
        raise ValueError(msg)
    site_config = load_site_config(site_paths.site_root)
    model_config = ModelConfig(cli_model=model, site_config=site_config)
    if client is None:
        client = genai.Client(api_key=gemini_api_key)
    try:
        text_client = client
        vision_client = client
        embedding_client = client
        embedding_model_name = model_config.get_model("embedding")
        cache_dir = Path(".egregora-cache") / site_paths.site_root.name
        enrichment_cache = EnrichmentCache(cache_dir)
        checkpoint_store = CheckpointStore(site_paths.site_root / ".egregora" / "checkpoints")
        logger.info("[bold cyan]📦 Parsing export:[/] %s", zip_path)
        group_name, chat_file = discover_chat_file(zip_path)
        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))
        logger.info("[yellow]👥 Discovered chat[/]: %s [dim](source: %s)[/]", group_name, chat_file)
        export = WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=datetime.now().date(),
            chat_file=chat_file,
            media_files=[],
        )
        messages_table = parse_export(export, timezone=timezone)
        total_messages = messages_table.count().execute()
        logger.info("[green]✅ Loaded[/] %s messages after parsing", total_messages)
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
            logger.info("[magenta]🧾 No /egregora commands detected in this export[/]")
        logger.info("[cyan]🖼️  Processing avatar commands...[/]")
        avatar_results = process_avatar_commands(
            messages_table=messages_table,
            zip_path=zip_path,
            docs_dir=site_paths.docs_dir,
            profiles_dir=site_paths.profiles_dir,
            group_slug=str(group_slug),
            vision_client=vision_client,
            model=model_config.get_model("enricher_vision"),
        )
        if avatar_results:
            logger.info("[green]✓ Processed[/] %s avatar command(s)", len(avatar_results))
            for result in avatar_results.values():
                logger.info("  %s", result)
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
                logger.info("📅 [cyan]Filtering[/] messages from %s to %s", from_date, to_date)
            elif from_date:
                messages_table = messages_table.filter(messages_table.timestamp.date() >= from_date)
                logger.info("📅 [cyan]Filtering[/] messages from %s onwards", from_date)
            elif to_date:
                messages_table = messages_table.filter(messages_table.timestamp.date() <= to_date)
                logger.info("📅 [cyan]Filtering[/] messages up to %s", to_date)
            filtered_count = messages_table.count().execute()
            removed_by_date = original_count - filtered_count
            if removed_by_date > 0:
                logger.info(
                    "🗓️  [yellow]Filtered out[/] %s messages by date (kept %s)",
                    removed_by_date,
                    filtered_count,
                )
            else:
                logger.info("[green]✓ All[/] %s messages are within the specified date range", filtered_count)
        logger.info("🎯 [bold cyan]Grouping messages by period[/]: %s", period)
        periods = group_by_period(messages_table, period)
        if not periods:
            logger.info("[yellow]No periods found after grouping[/]")
            return {}
        results = {}
        posts_dir = site_paths.posts_dir
        profiles_dir = site_paths.profiles_dir
        site_paths.enriched_dir.mkdir(parents=True, exist_ok=True)
        for period_key in sorted(periods.keys()):
            period_table = periods[period_key]
            period_count = period_table.count().execute()
            logger.info("➡️  [bold]%s[/] — %s messages", period_key, period_count)
            checkpoint_data = checkpoint_store.load(period_key) if resume else {"steps": {}}
            steps_state = checkpoint_data.get("steps", {})
            period_table, media_mapping = extract_and_replace_media(
                period_table, zip_path, site_paths.docs_dir, posts_dir, str(group_slug)
            )
            logger.info("Processing %s...", period_key)
            enriched_path = site_paths.enriched_dir / f"{period_key}-enriched.csv"
            if enable_enrichment:
                logger.info("✨ [cyan]Enriching[/] period %s", period_key)
                if resume and steps_state.get("enrichment") == StepStatus.COMPLETED.value:
                    try:
                        enriched_table = _load_enriched_table(enriched_path, period_table.schema())
                        logger.info("Loaded cached enrichment for %s", period_key)
                    except FileNotFoundError:
                        logger.info("Cached enrichment missing; regenerating %s", period_key)
                        if resume:
                            steps_state = checkpoint_store.update_step(
                                period_key, "enrichment", "in_progress"
                            )["steps"]
                        enriched_table = enrich_table(
                            period_table,
                            media_mapping,
                            text_client,
                            vision_client,
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
                        text_client,
                        vision_client,
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
            if resume and steps_state.get("writing") == StepStatus.COMPLETED.value:
                logger.info("Resuming posts for %s from existing files", period_key)
                existing_posts = sorted(posts_dir.glob(f"{period_key}-*.md"))
                result = {"posts": [str(p) for p in existing_posts], "profiles": []}
            else:
                if resume:
                    steps_state = checkpoint_store.update_step(period_key, "writing", "in_progress")["steps"]
                writer_config = WriterConfig(
                    output_dir=posts_dir,
                    profiles_dir=profiles_dir,
                    rag_dir=site_paths.rag_dir,
                    enable_rag=True,
                    retrieval_mode=retrieval_mode,
                    retrieval_nprobe=retrieval_nprobe,
                    retrieval_overfetch=retrieval_overfetch,
                )
                result = write_posts_for_period(enriched_table, period_key, embedding_client, writer_config)
                if resume:
                    steps_state = checkpoint_store.update_step(period_key, "writing", "completed")["steps"]
            results[period_key] = result
            post_count = len(result.get("posts", []))
            profile_count = len(result.get("profiles", []))
            logger.info(
                "[green]✔ Generated[/] %s posts / %s profiles for %s", post_count, profile_count, period_key
            )
        if enable_enrichment and results:
            logger.info("[bold cyan]📚 Indexing media enrichments into RAG...[/]")
            try:
                rag_dir = site_paths.rag_dir
                store = VectorStore(rag_dir / "chunks.parquet")
                media_chunks = index_all_media(
                    site_paths.docs_dir, store, embedding_model=embedding_model_name
                )
                if media_chunks > 0:
                    logger.info("[green]✓ Indexed[/] %s media chunks into RAG", media_chunks)
                else:
                    logger.info("[yellow]No media enrichments to index for this run[/]")
            except Exception as e:
                logger.exception("[red]Failed to index media into RAG:[/] %s", e)
        return results
    finally:
        try:
            if "enrichment_cache" in locals():
                enrichment_cache.close()
        finally:
            if client:
                client.close()


def process_whatsapp_export(
    zip_path: Path,
    output_dir: Path = Path("output"),
    period: str = "day",
    enable_enrichment: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
    timezone: str | ZoneInfo | None = None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Public entry point that manages DuckDB/Ibis backend state for processing.

    Args:
        zip_path: WhatsApp export ZIP file
        output_dir: Where to save posts and profiles
        period: "day", "week", or "month"
        enable_enrichment: Add URL/media context
        from_date: Only process messages from this date onwards (date object)
        to_date: Only process messages up to this date (date object)
        timezone: ZoneInfo timezone object (WhatsApp export phone timezone)
        gemini_api_key: Google Gemini API key
        model: Gemini model to use (overrides mkdocs.yml config)
        resume: Whether to resume from a previous run.
        batch_threshold: The threshold for switching to batch processing.
        retrieval_mode: The retrieval mode to use.
        retrieval_nprobe: The number of probes to use for retrieval.
        retrieval_overfetch: The overfetch factor to use for retrieval.

    Returns:
        Dict mapping period to {'posts': [...], 'profiles': [...]}

    """
    output_dir = output_dir.expanduser().resolve()
    site_paths = resolve_site_paths(output_dir)
    runtime_db_path = site_paths.site_root / ".egregora" / "pipeline.duckdb"
    runtime_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(runtime_db_path))
    backend = ibis.duckdb.from_connection(connection)
    options = getattr(ibis, "options", None)
    old_backend = getattr(options, "default_backend", None) if options else None
    try:
        if options is not None:
            options.default_backend = backend
        return _process_whatsapp_export(
            zip_path=zip_path,
            output_dir=output_dir,
            site_paths=site_paths,
            period=period,
            enable_enrichment=enable_enrichment,
            from_date=from_date,
            to_date=to_date,
            timezone=timezone,
            gemini_api_key=gemini_api_key,
            model=model,
            resume=resume,
            batch_threshold=batch_threshold,
            retrieval_mode=retrieval_mode,
            retrieval_nprobe=retrieval_nprobe,
            retrieval_overfetch=retrieval_overfetch,
            client=client,
        )
    finally:
        if options is not None:
            options.default_backend = old_backend
        connection.close()
