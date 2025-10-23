"""Simple enrichment: add LLM-described media/URLs as DataFrame rows."""

import re
from datetime import timedelta
from pathlib import Path
import polars as pl
from google import genai


URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text."""
    if not text:
        return []
    return URL_PATTERN.findall(text)


def extract_media(text: str) -> list[str]:
    """Extract media file references from WhatsApp messages."""
    if not text:
        return []

    media_patterns = [
        r'<attached: (.+?)>',
        r'\(file attached\)',
        r'IMG-\d+-WA\d+\.\w+',
        r'VID-\d+-WA\d+\.\w+',
        r'AUD-\d+-WA\d+\.\w+',
        r'PTT-\d+-WA\d+\.\w+',
    ]

    media = []
    for pattern in media_patterns:
        matches = re.findall(pattern, text)
        media.extend(matches)

    return media


async def describe_url(url: str, client: genai.Client) -> str:
    """Ask LLM to describe a URL's content."""
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=f"Briefly describe what this URL is about (1-2 sentences): {url}"
        )
        return response.text.strip()
    except Exception as e:
        return f"[Failed to fetch URL: {str(e)}]"


async def describe_media(media_ref: str, client: genai.Client) -> str:
    """Ask LLM to describe media content."""
    return f"[Media file: {media_ref}]"


async def enrich_dataframe(
    df: pl.DataFrame,
    client: genai.Client,
    enable_url: bool = True,
    enable_media: bool = True,
    max_enrichments: int = 50,
) -> pl.DataFrame:
    """
    Add enrichment rows to DataFrame for URLs and media.

    Returns new DataFrame with additional rows authored by 'egregora'.
    """
    if df.is_empty():
        return df

    new_rows = []
    enrichment_count = 0

    for row in df.iter_rows(named=True):
        if enrichment_count >= max_enrichments:
            break

        message = row.get("message", "")
        timestamp = row["timestamp"]

        if enable_url:
            urls = extract_urls(message)
            for url in urls[:3]:  # Max 3 URLs per message
                if enrichment_count >= max_enrichments:
                    break

                description = await describe_url(url, client)
                new_rows.append({
                    "timestamp": timestamp + timedelta(seconds=1),
                    "author": "egregora",
                    "message": f"[URL Context] {url}\n{description}",
                })
                enrichment_count += 1

        if enable_media:
            media = extract_media(message)
            for media_ref in media[:2]:  # Max 2 media per message
                if enrichment_count >= max_enrichments:
                    break

                description = await describe_media(media_ref, client)
                new_rows.append({
                    "timestamp": timestamp + timedelta(seconds=1),
                    "author": "egregora",
                    "message": description,
                })
                enrichment_count += 1

    if not new_rows:
        return df

    enrichment_df = pl.DataFrame(new_rows)

    combined = pl.concat([df, enrichment_df])
    combined = combined.sort("timestamp")

    return combined
