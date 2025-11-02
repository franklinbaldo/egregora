"""Ultra-simple pipeline: parse → anonymize → group → enrich → write."""

import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path

import duckdb
import ibis
from google import genai
from ibis.expr.types import Table

from egregora.augmentation.enrichment import enrich_table, extract_and_replace_media
from egregora.augmentation.profiler import filter_opted_out_authors, process_commands
from egregora.config import ModelConfig, SitePaths, load_site_config, resolve_site_paths
from egregora.core.models import WhatsAppExport
from egregora.core.types import GroupSlug
from egregora.generation.writer import write_posts_for_period
from egregora.ingestion.parser import extract_commands, filter_egregora_messages, parse_export
from egregora.knowledge.rag import VectorStore, index_all_media
from egregora.utils.batch import (
    GeminiBatchClient,  # noqa: F401  # Backwards compatibility for tests
)
from egregora.utils.cache import EnrichmentCache
from egregora.utils.checkpoints import CheckpointStore
from egregora.utils.gemini_dispatcher import GeminiDispatcher

logger = logging.getLogger(__name__)

SINGLE_DIGIT_THRESHOLD = 10


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP and extract group name."""

    with zipfile.ZipFile(zip_path) as zf:
        # Collect all .txt candidates
        candidates = []
        for member in zf.namelist():
            if member.endswith(".txt") and not member.startswith("__"):
                # Generic pattern to capture group name from WhatsApp chat files
                pattern = r"WhatsApp(?: Chat with|.*) (.+)\.txt"
                match = re.match(pattern, Path(member).name)

                # Calculate heuristic score: file size + pattern match bonus
                file_info = zf.getinfo(member)
                score = file_info.file_size

                if match:
                    # Pattern match gives high priority
                    score += 1_000_000
                    group_name = match.group(1)
                else:
                    # No pattern match, use stem as fallback
                    group_name = Path(member).stem

                candidates.append((score, group_name, member))

        if not candidates:
            raise ValueError(f"No WhatsApp chat file found in {zip_path}")

        # Sort by score (descending) and pick the best
        candidates.sort(reverse=True, key=lambda x: x[0])
        _, group_name, member = candidates[0]

        return group_name, member


def period_has_posts(period_key: str, posts_dir: Path) -> bool:
    """Check if posts already exist for this period."""
    if not posts_dir.exists():
        return False

    # Look for files matching {period_key}-*.md
    pattern = f"{period_key}-*.md"
    existing_posts = list(posts_dir.glob(pattern))

    return len(existing_posts) > 0


def group_by_period(table: Table, period: str = "day") -> dict[str, Table]:
    """
    Group Table by time period.

    Args:
        table: Table with timestamp column
        period: "day", "week", or "month"

    Returns:
        Dict mapping period string to Table
    """
    if table.count().execute() == 0:
        return {}

    if period == "day":
        table = table.mutate(period=table.timestamp.date().cast("string"))
    elif period == "week":
        # ISO week format: YYYY-Wnn
        # Use ISO week-year to handle weeks that cross calendar year boundaries
        # (e.g., 2024-W52 can include days from early January 2025)
        week_num = table.timestamp.week_of_year()

        # ISO week-year: if week number is 52/53 and month is January,
        # the ISO year is previous calendar year
        # if week number is 1 and month is December,
        # the ISO year is next calendar year
        iso_year = ibis.cases(
            ((week_num >= 52) & (table.timestamp.month() == 1), table.timestamp.year() - 1),  # noqa: PLR2004
            ((week_num == 1) & (table.timestamp.month() == 12), table.timestamp.year() + 1),  # noqa: PLR2004
            else_=table.timestamp.year()
        )

        year_str = iso_year.cast("string")
        week_str = ibis.ifelse(
            week_num < SINGLE_DIGIT_THRESHOLD,
            ibis.literal("0") + week_num.cast("string"),
            week_num.cast("string"),
        )
        table = table.mutate(period=year_str + ibis.literal("-W") + week_str)
    elif period == "month":
        # Format: YYYY-MM
        year_str = table.timestamp.year().cast("string")
        month_num = table.timestamp.month()
        # Zero-pad month: use lpad to ensure 2 digits
        month_str = ibis.ifelse(
            month_num < SINGLE_DIGIT_THRESHOLD,
            ibis.literal("0") + month_num.cast("string"),
            month_num.cast("string"),
        )
        table = table.mutate(period=year_str + ibis.literal("-") + month_str)
    else:
        raise ValueError(f"Unknown period: {period}")

    grouped = {}
    # Get unique period values, sorted
    period_values = sorted(table.select("period").distinct().execute()["period"].tolist())

    for period_value in period_values:
        period_table = table.filter(table.period == period_value).drop("period")
        grouped[period_value] = period_table

    return grouped


def _process_whatsapp_export(  # noqa: PLR0912, PLR0913, PLR0915
    zip_path: Path,
    output_dir: Path,
    *,
    site_paths: SitePaths,
    period: str = "day",
    enable_enrichment: bool = True,
    from_date=None,
    to_date=None,
    timezone=None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """
    Complete pipeline: ZIP → posts + profiles.

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

    def _load_enriched_table(path: Path, schema: Table.schema) -> Table:
        if not path.exists():
            raise FileNotFoundError(path)
        return ibis.read_csv(str(path), table_schema=schema)

    # Validate MkDocs scaffold exists before proceeding
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

    # Load site config and create model config
    site_config = load_site_config(site_paths.site_root)
    model_config = ModelConfig(cli_model=model, site_config=site_config)

    # If a client is not provided, create a new one.
    # This allows injecting a mock or recorder client for testing.
    if client is None:
        client = genai.Client(api_key=gemini_api_key)

    try:
        text_batch_client = GeminiDispatcher(
            client, model_config.get_model("enricher"), batch_threshold=batch_threshold
        )
        vision_batch_client = GeminiDispatcher(
            client, model_config.get_model("enricher_vision"), batch_threshold=batch_threshold
        )
        embedding_model_name = model_config.get_model("embedding")
        embedding_batch_client = GeminiDispatcher(
            client, embedding_model_name, batch_threshold=batch_threshold
        )
        embedding_dimensionality = model_config.embedding_output_dimensionality
        cache_dir = Path(".egregora-cache") / site_paths.site_root.name
        enrichment_cache = EnrichmentCache(cache_dir)
        checkpoint_store = CheckpointStore(site_paths.site_root / ".egregora" / "checkpoints")

        logger.info(f"[bold cyan]📦 Parsing export:[/] {zip_path}")
        group_name, chat_file = discover_chat_file(zip_path)
        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))
        logger.info(f"[yellow]👥 Discovered chat[/]: {group_name} [dim](source: {chat_file})[/]")

        export = WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=datetime.now().date(),
            chat_file=chat_file,
            media_files=[],
        )

        # Parse and anonymize (with timezone from phone)
        messages_table = parse_export(export, timezone=timezone)
        total_messages = messages_table.count().execute()
        logger.info(f"[green]✅ Loaded[/] {total_messages} messages after parsing")

        # Ensure key directories exist and live inside docs/
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

        # Extract and process egregora commands (before filtering)
        commands = extract_commands(messages_table)
        if commands:
            process_commands(commands, site_paths.profiles_dir)
            logger.info(f"[magenta]🧾 Processed[/] {len(commands)} /egregora commands")
        else:
            logger.info("[magenta]🧾 No /egregora commands detected in this export[/]")

        # Remove ALL /egregora messages (commands + ad-hoc exclusions)
        messages_table, egregora_removed = filter_egregora_messages(messages_table)
        if egregora_removed:
            logger.info(f"[yellow]🧹 Removed[/] {egregora_removed} /egregora messages")

        # Filter out opted-out authors EARLY (before any processing)
        messages_table, removed_count = filter_opted_out_authors(
            messages_table, site_paths.profiles_dir
        )
        if removed_count > 0:
            logger.warning(f"⚠️  {removed_count} messages removed from opted-out users")

        # Filter by date range if specified
        if from_date or to_date:
            original_count = messages_table.count().execute()

            if from_date and to_date:
                messages_table = messages_table.filter(
                    (messages_table.timestamp.date() >= from_date)
                    & (messages_table.timestamp.date() <= to_date)
                )
                logger.info(f"📅 [cyan]Filtering[/] messages from {from_date} to {to_date}")
            elif from_date:
                messages_table = messages_table.filter(messages_table.timestamp.date() >= from_date)
                logger.info(f"📅 [cyan]Filtering[/] messages from {from_date} onwards")
            elif to_date:
                messages_table = messages_table.filter(messages_table.timestamp.date() <= to_date)
                logger.info(f"📅 [cyan]Filtering[/] messages up to {to_date}")

            filtered_count = messages_table.count().execute()
            removed_by_date = original_count - filtered_count

            if removed_by_date > 0:
                logger.info(
                    f"🗓️  [yellow]Filtered out[/] {removed_by_date} messages by date (kept {filtered_count})"
                )
            else:
                logger.info(
                    f"[green]✓ All[/] {filtered_count} messages are within the specified date range"
                )

        # Group by period first (media extraction handled per-period)
        logger.info(f"🎯 [bold cyan]Grouping messages by period[/]: {period}")
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
            logger.info(f"➡️  [bold]{period_key}[/] — {period_count} messages")

            checkpoint_data = checkpoint_store.load(period_key) if resume else {"steps": {}}
            steps_state = checkpoint_data.get("steps", {})

            period_table, media_mapping = extract_and_replace_media(
                period_table,
                zip_path,
                site_paths.docs_dir,
                posts_dir,
                str(group_slug),
            )

            logger.info(f"Processing {period_key}...")

            enriched_path = site_paths.enriched_dir / f"{period_key}-enriched.csv"

            if enable_enrichment:
                logger.info(f"✨ [cyan]Enriching[/] period {period_key}")
                if resume and steps_state.get("enrichment") == "completed":
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
                            text_batch_client,
                            vision_batch_client,
                            enrichment_cache,
                            site_paths.docs_dir,
                            posts_dir,
                            model_config,
                        )
                        enriched_table.execute().to_csv(enriched_path, index=False)
                        if resume:
                            steps_state = checkpoint_store.update_step(
                                period_key, "enrichment", "completed"
                            )["steps"]
                else:
                    if resume:
                        steps_state = checkpoint_store.update_step(
                            period_key, "enrichment", "in_progress"
                        )["steps"]
                    enriched_table = enrich_table(
                        period_table,
                        media_mapping,
                        text_batch_client,
                        vision_batch_client,
                        enrichment_cache,
                        site_paths.docs_dir,
                        posts_dir,
                        model_config,
                    )
                    enriched_table.execute().to_csv(enriched_path, index=False)
                    if resume:
                        steps_state = checkpoint_store.update_step(
                            period_key, "enrichment", "completed"
                        )["steps"]
            else:
                enriched_table = period_table
                enriched_table.execute().to_csv(enriched_path, index=False)

            if resume and steps_state.get("writing") == "completed":
                logger.info("Resuming posts for %s from existing files", period_key)
                existing_posts = sorted(posts_dir.glob(f"{period_key}-*.md"))
                result = {
                    "posts": [str(p) for p in existing_posts],
                    "profiles": [],
                }
            else:
                if resume:
                    steps_state = checkpoint_store.update_step(
                        period_key, "writing", "in_progress"
                    )["steps"]
                result = write_posts_for_period(
                    enriched_table,
                    period_key,
                    client,
                    embedding_batch_client,
                    posts_dir,
                    profiles_dir,
                    site_paths.rag_dir,
                    model_config,
                    enable_rag=True,
                    embedding_output_dimensionality=embedding_dimensionality,
                    retrieval_mode=retrieval_mode,
                    retrieval_nprobe=retrieval_nprobe,
                    retrieval_overfetch=retrieval_overfetch,
                )
                if resume:
                    steps_state = checkpoint_store.update_step(period_key, "writing", "completed")[
                        "steps"
                    ]

            results[period_key] = result
            logger.info(
                f"[green]✔ Generated[/] {len(result.get('posts', []))} posts / {len(result.get('profiles', []))} profiles for {period_key}"
            )

        # Index all media enrichments into RAG (if enrichment was enabled)
        if enable_enrichment and results:
            logger.info("[bold cyan]📚 Indexing media enrichments into RAG...[/]")
            try:
                rag_dir = site_paths.rag_dir
                store = VectorStore(rag_dir / "chunks.parquet")
                media_chunks = index_all_media(
                    site_paths.docs_dir,
                    embedding_batch_client,
                    store,
                    embedding_model=embedding_batch_client.default_model,
                    output_dimensionality=embedding_dimensionality,
                )
                if media_chunks > 0:
                    logger.info(f"[green]✓ Indexed[/] {media_chunks} media chunks into RAG")
                else:
                    logger.info("[yellow]No media enrichments to index for this run[/]")
            except Exception as e:
                logger.error(f"[red]Failed to index media into RAG:[/] {e}")

        return results
    finally:
        try:
            if "enrichment_cache" in locals():
                enrichment_cache.close()
        finally:
            if client:
                client.close()


def process_whatsapp_export(  # noqa: PLR0912, PLR0913
    zip_path: Path,
    output_dir: Path = Path("output"),
    period: str = "day",
    enable_enrichment: bool = True,
    from_date=None,
    to_date=None,
    timezone=None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    """
    Public entry point that manages DuckDB/Ibis backend state for processing.

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
