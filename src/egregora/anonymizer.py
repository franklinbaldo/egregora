"""Simple UUID5-based anonymization for authors and mentions."""

import re
import uuid

import polars as pl

NAMESPACE_AUTHOR = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

MENTION_PATTERN = re.compile(r"\u2068(?P<name>.*?)\u2069")


def anonymize_author(author: str) -> str:
    """Generate deterministic UUID5 pseudonym for author."""
    normalized = author.strip().lower()
    author_uuid = uuid.uuid5(NAMESPACE_AUTHOR, normalized)
    return author_uuid.hex[:8]


def anonymize_mentions(text: str) -> str:
    """Replace WhatsApp mentions (Unicode markers) with UUID5 pseudonyms."""
    if not text or "\u2068" not in text:
        return text

    def replace_mention(match):
        name = match.group("name")
        pseudonym = anonymize_author(name)
        return pseudonym

    return MENTION_PATTERN.sub(replace_mention, text)


def anonymize_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Anonymize author column and mentions in message column using vectorial operations."""

    anonymized = df.with_columns(
        [
            pl.col("author")
            .map_elements(lambda x: anonymize_author(x) if x else "system", return_dtype=pl.Utf8)
            .alias("author")
        ]
    )

    if "message" in anonymized.columns:
        anonymized = anonymized.with_columns(
            [
                pl.col("message")
                .map_elements(lambda x: anonymize_mentions(x) if x else "", return_dtype=pl.Utf8)
                .alias("message")
            ]
        )

    return anonymized
