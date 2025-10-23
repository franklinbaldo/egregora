"""Ultra-simple pipeline: parse → anonymize → group → enrich → write."""

import zipfile
from pathlib import Path
from datetime import datetime
import polars as pl
from google import genai

from .parser import parse_export
from .models import WhatsAppExport
from .types import GroupSlug
from .enricher import extract_and_replace_media, enrich_dataframe
from .writer import write_posts_for_period


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
) -> dict[str, list[str]]:
    """
    Complete pipeline: ZIP → posts.

    Args:
        zip_path: WhatsApp export ZIP file
        output_dir: Where to save posts
        period: "day", "week", or "month"
        enable_enrichment: Add URL/media context
        gemini_api_key: Google Gemini API key

    Returns:
        Dict mapping period to list of saved post paths
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

    for period_key, period_df in periods.items():
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

        posts_dir = output_dir / "posts"
        saved_posts = await write_posts_for_period(
            enriched_df,
            period_key,
            client,
            posts_dir,
        )

        results[period_key] = saved_posts

    return results
