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

import ibis
from ibis.expr.types import Table

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


def anonymize_dataframe(df: Table) -> Table:
    """Anonymize author column and mentions in message column using vectorial operations."""

    # 1. Anonymize Authors
    # Get unique author names, create a mapping, and then replace using CASE statements
    unique_authors_df = df.select("author").distinct().execute()

    # ibis executes to a pandas DataFrame; get the author column
    unique_authors = unique_authors_df["author"].dropna().tolist()
    author_mapping = {author: anonymize_author(author) for author in unique_authors}

    # Build a CASE expression for author replacement
    # Start with the author column
    author_expr = df.author

    # Chain .substitute() calls for each mapping
    # Ibis has a .substitute() method that's perfect for this
    anonymized_author = author_expr.substitute(author_mapping, else_=SYSTEM_AUTHOR)

    # Apply the anonymized author column
    anonymized_df = df.mutate(author=anonymized_author)

    # 2. Anonymize Mentions in Messages
    if "message" in anonymized_df.columns:
        # Register the anonymize_mentions function as a UDF
        # Note: For DuckDB backend, we can use Python UDFs
        @ibis.udf.scalar.python
        def anonymize_mentions_udf(text: str) -> str:
            """UDF wrapper for anonymize_mentions."""
            return anonymize_mentions(text) if text else text

        anonymized_df = anonymized_df.mutate(message=anonymize_mentions_udf(anonymized_df.message))

    return anonymized_df
