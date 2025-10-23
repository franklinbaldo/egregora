"""Ultra-simple pipeline: parse → anonymize → group → enrich → write."""

import logging
import zipfile
from pathlib import Path
from datetime import datetime
import polars as pl
from google import genai

from .parser import parse_export, extract_commands
from .models import WhatsAppExport
from .types import GroupSlug
from .enricher import extract_and_replace_media, enrich_dataframe
from .writer import write_posts_for_period
from .profiler import process_commands


logger = logging.getLogger(__name__)


def discover_chat_file(zip_path: Path) -> tuple[str, str]:
    """Find the chat .txt file in the ZIP and extract group name."""
    import re

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith(".txt") and not member.startswith("__"):
                patterns = [
                    r"Conversa do WhatsApp com (.+)\.txt",
                    r"WhatsApp Chat with (.+)\.txt",
                    r"Chat de WhatsApp con (.+)\.txt",
                ]

                for pattern in patterns:
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


def group_by_period(df: pl.DataFrame, period: str = "day") -> dict[str, pl.DataFrame]:
    """
    Group DataFrame by time period.

    Args:
        df: DataFrame with timestamp column
        period: "day", "week", or "month"

    Returns:
        Dict mapping period string to DataFrame
    """
    if df.is_empty():
        return {}

    if period == "day":
        df = df.with_columns(
            pl.col("timestamp").dt.date().cast(pl.Utf8).alias("period")
        )
    elif period == "week":
        df = df.with_columns(
            (
                pl.col("timestamp").dt.year().cast(pl.Utf8)
                + "-W"
                + pl.col("timestamp").dt.week().cast(pl.Utf8)
            ).alias("period")
        )
    elif period == "month":
        df = df.with_columns(
            (
                pl.col("timestamp").dt.year().cast(pl.Utf8)
                + "-"
                + pl.col("timestamp").dt.month().cast(pl.Utf8).str.zfill(2)
            ).alias("period")
        )
    else:
        raise ValueError(f"Unknown period: {period}")

    grouped = {}
    for period_value in df["period"].unique().sort():
        period_df = df.filter(pl.col("period") == period_value).drop("period")
        grouped[period_value] = period_df

    return grouped


async def process_whatsapp_export(
    zip_path: Path,
    output_dir: Path = Path("output"),
    period: str = "day",
    enable_enrichment: bool = True,
    gemini_api_key: str | None = None,
) -> dict[str, dict[str, list[str]]]:
    """
    Complete pipeline: ZIP → posts + profiles.

    Args:
        zip_path: WhatsApp export ZIP file
        output_dir: Where to save posts and profiles
        period: "day", "week", or "month"
        enable_enrichment: Add URL/media context
        gemini_api_key: Google Gemini API key

    Returns:
        Dict mapping period to {'posts': [...], 'profiles': [...]}
    """

    client = genai.Client(api_key=gemini_api_key)

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

    # Parse and anonymize
    df = parse_export(export)

    # Extract and process egregora commands (before grouping)
    commands = extract_commands(df)
    if commands:
        profiles_dir = output_dir / "profiles"
        process_commands(commands, profiles_dir)
        logger.info(f"Processed {len(commands)} egregora commands")

    # Extract media from ZIP and replace mentions BEFORE grouping
    df, media_mapping = extract_and_replace_media(
        df,
        zip_path,
        output_dir,
        str(group_slug),
    )

    # Group by period (after media replacement)
    periods = group_by_period(df, period)

    results = {}
    posts_dir = output_dir / "posts"
    profiles_dir = output_dir / "profiles"

    for period_key, period_df in periods.items():
        # Early exit: skip if posts already exist for this period
        if period_has_posts(period_key, posts_dir):
            logger.info(f"Skipping {period_key} - posts already exist")
            existing_posts = list(posts_dir.glob(f"{period_key}-*.md"))
            results[period_key] = {"posts": [str(p) for p in existing_posts], "profiles": []}
            continue

        logger.info(f"Processing {period_key}...")

        enriched_df = period_df

        # Optionally add LLM-generated enrichment rows
        if enable_enrichment:
            enriched_df = await enrich_dataframe(
                period_df,
                media_mapping,
                client,
            )

        enriched_dir = output_dir / "enriched"
        enriched_dir.mkdir(parents=True, exist_ok=True)
        enriched_path = enriched_dir / f"{period_key}-enriched.csv"
        enriched_df.write_csv(enriched_path)

        result = await write_posts_for_period(
            enriched_df,
            period_key,
            client,
            posts_dir,
            profiles_dir,
            output_dir / "rag",
        )

        results[period_key] = result

    return results
