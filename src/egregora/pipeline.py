"""Ultra-simple pipeline: parse → anonymize → group → enrich → write."""

import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path

import ibis
from google import genai
from ibis.expr.types import Table

from .enricher import enrich_dataframe, extract_and_replace_media
from .model_config import ModelConfig, load_site_config
from .models import WhatsAppExport
from .parser import extract_commands, filter_egregora_messages, parse_export
from .profiler import filter_opted_out_authors, process_commands
from .types import GroupSlug
from .writer import write_posts_for_period

logger = logging.getLogger(__name__)


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP and extract group name."""

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith(".txt") and not member.startswith("__"):
                # Generic pattern to capture group name from WhatsApp chat files
                pattern = r"WhatsApp(?: Chat with|.*) (.+)\.txt"
                match = re.match(pattern, Path(member).name)
                if match:
                    return match.group(1), member
                return Path(member).stem, member

    raise ValueError(f"No WhatsApp chat file found in {zip_path}")


def period_has_posts(period_key: str, posts_dir: Path) -> bool:
    """Check if posts already exist for this period."""
    if not posts_dir.exists():
        return False

    # Look for files matching {period_key}-*.md
    pattern = f"{period_key}-*.md"
    existing_posts = list(posts_dir.glob(pattern))

    return len(existing_posts) > 0


def group_by_period(df: Table, period: str = "day") -> dict[str, Table]:
    """
    Group Table by time period.

    Args:
        df: Table with timestamp column
        period: "day", "week", or "month"

    Returns:
        Dict mapping period string to Table
    """
    if df.count().execute() == 0:
        return {}

    if period == "day":
        df = df.mutate(period=df.timestamp.date().cast("string"))
    elif period == "week":
        # ISO week format: YYYY-Wnn
        year_str = df.timestamp.year().cast("string")
        week_str = df.timestamp.week_of_year().cast("string")
        df = df.mutate(period=year_str + "-W" + week_str)
    elif period == "month":
        # Format: YYYY-MM
        year_str = df.timestamp.year().cast("string")
        month_num = df.timestamp.month()
        # Zero-pad month: use lpad to ensure 2 digits
        month_str = ibis.case().when(month_num < 10, "0" + month_num.cast("string")).else_(month_num.cast("string")).end()
        df = df.mutate(period=year_str + "-" + month_str)
    else:
        raise ValueError(f"Unknown period: {period}")

    grouped = {}
    # Get unique period values, sorted
    period_values = sorted(df.period.distinct().execute().tolist())

    for period_value in period_values:
        period_df = df.filter(df.period == period_value).drop("period")
        grouped[period_value] = period_df

    return grouped


async def process_whatsapp_export(  # noqa: PLR0912, PLR0913, PLR0915
    zip_path: Path,
    output_dir: Path = Path("output"),
    period: str = "day",
    enable_enrichment: bool = True,
    from_date=None,
    to_date=None,
    timezone=None,
    gemini_api_key: str | None = None,
    model: str | None = None,
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

    Returns:
        Dict mapping period to {'posts': [...], 'profiles': [...]}
    """

    client = genai.Client(api_key=gemini_api_key)

    # Load site config and create model config
    site_config = load_site_config(output_dir)
    model_config = ModelConfig(cli_model=model, site_config=site_config)

    try:
        group_name, chat_file = discover_chat_file(zip_path)
        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))

        export = WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=datetime.now().date(),
            chat_file=chat_file,
            media_files=[],
        )

        # Parse and anonymize (with timezone from phone)
        df = parse_export(export, timezone=timezone)

        # Extract and process egregora commands (before filtering)
        commands = extract_commands(df)
        if commands:
            profiles_dir = output_dir / "profiles"
            process_commands(commands, profiles_dir)
            logger.info(f"Processed {len(commands)} egregora commands")

        # Remove ALL /egregora messages (commands + ad-hoc exclusions)
        df, egregora_removed = filter_egregora_messages(df)

        # Filter out opted-out authors EARLY (before any processing)
        profiles_dir = output_dir / "profiles"
        df, removed_count = filter_opted_out_authors(df, profiles_dir)
        if removed_count > 0:
            logger.warning(f"⚠️  Total: {removed_count} messages removed from opted-out users")

        # Filter by date range if specified
        if from_date or to_date:
            original_count = df.count().execute()

            if from_date and to_date:
                df = df.filter(
                    (df.timestamp.date() >= from_date)
                    & (df.timestamp.date() <= to_date)
                )
                logger.info(f"📅 Filtering messages from {from_date} to {to_date}")
            elif from_date:
                df = df.filter(df.timestamp.date() >= from_date)
                logger.info(f"📅 Filtering messages from {from_date} onwards")
            elif to_date:
                df = df.filter(df.timestamp.date() <= to_date)
                logger.info(f"📅 Filtering messages up to {to_date}")

            filtered_count = df.count().execute()
            removed_by_date = original_count - filtered_count

            if removed_by_date > 0:
                logger.info(
                    f"🗓️  Filtered out {removed_by_date} messages by date (kept {filtered_count})"
                )
            else:
                logger.info(f"✓ All {filtered_count} messages are within the specified date range")

        # Group by period first (media extraction handled per-period)
        periods = group_by_period(df, period)
        if not periods:
            logger.info("No periods found after grouping")
            return {}

        results = {}
        posts_dir = output_dir / "posts"
        profiles_dir = output_dir / "profiles"

        for period_key in sorted(periods.keys()):
            period_df = periods[period_key]

            # Early exit: skip if posts already exist for this period
            if period_has_posts(period_key, posts_dir):
                logger.info(f"Skipping {period_key} - posts already exist")
                existing_posts = list(posts_dir.glob(f"{period_key}-*.md"))
                results[period_key] = {"posts": [str(p) for p in existing_posts], "profiles": []}
                continue

            # Extract and replace media for this period only
            period_df, media_mapping = extract_and_replace_media(
                period_df,
                zip_path,
                output_dir,
                str(group_slug),
            )

            logger.info(f"Processing {period_key}...")

            enriched_df = period_df

            # Optionally add LLM-generated enrichment rows
            if enable_enrichment:
                enriched_df = await enrich_dataframe(
                    period_df,
                    media_mapping,
                    client,
                    output_dir,
                    model_config,
                )

            enriched_dir = output_dir / "enriched"
            enriched_dir.mkdir(parents=True, exist_ok=True)
            enriched_path = enriched_dir / f"{period_key}-enriched.csv"
            # Write CSV using Ibis - need to execute to pandas first
            enriched_df.execute().to_csv(enriched_path, index=False)

            result = await write_posts_for_period(
                enriched_df,
                period_key,
                client,
                posts_dir,
                profiles_dir,
                output_dir / "rag",
                model_config,
            )

            results[period_key] = result

        return results
    finally:
        client.close()
