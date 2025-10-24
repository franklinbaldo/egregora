"""Simple UUID5-based anonymization for authors and mentions.

Privacy-first approach: All author names are converted to UUID5 pseudonyms
before any LLM interaction. This ensures real names never reach the LLM.

Documentation:
- Privacy & Anonymization: docs/features/anonymization.md
- Architecture (Privacy Boundary): docs/guides/architecture.md#2-anonymizer-anonymizerpy
- Core Concepts: docs/getting-started/concepts.md#privacy-model
"""
import re
import uuid

import polars as pl

NAMESPACE_AUTHOR = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
SYSTEM_AUTHOR = "system"

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

    # 1. Anonymize Authors
    # Get unique author names, create a mapping, and then replace in one go.
    unique_authors = df.select(pl.col("author").unique()).to_series().drop_nulls().to_list()
    author_mapping = {author: anonymize_author(author) for author in unique_authors}

    anonymized_df = df.with_columns(
        pl.col("author").replace(author_mapping).fill_null(SYSTEM_AUTHOR)
    )

    # 2. Anonymize Mentions in Messages
    if "message" in anonymized_df.columns:
        anonymized_df = anonymized_df.with_columns(
            pl.col("message")
            .map_elements(anonymize_mentions, return_dtype=pl.Utf8)
            .alias("message")
        )

    return anonymized_df
