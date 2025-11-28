"""Privacy-preserving anonymization utilities for IR tables."""

from __future__ import annotations

import re

import ibis
from ibis.expr.types import Table

DEFAULT_REDACTED = "[redacted]"
MENTION_PATTERN = re.compile("\\u2068(?P<name>.*?)\\u2069")


def _sanitize_mentions(text: str, mapping: dict[str, str]) -> str:
    if not text or "\u2068" not in text:
        return text

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        return mapping.get(name, DEFAULT_REDACTED)

    return MENTION_PATTERN.sub(replace, text)


def anonymize_table(
    table: Table,
    *,
    redact_token: str = DEFAULT_REDACTED,
    enabled: bool = True,
) -> Table:
    """Redact author_raw values while preserving deterministic author_uuid.

    Args:
        table: Input table with author_raw and author_uuid columns
        redact_token: Token to use for redacted values
        enabled: If False, skip anonymization and return table as-is

    Returns:
        Table with author_raw anonymized (if enabled)
    """
    # If anonymization is disabled, return table unchanged
    if not enabled:
        return table

    required = {"author_raw", "author_uuid"}
    missing = required - set(table.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        msg = f"Table is missing required columns for anonymization: {missing_cols}"
        raise ValueError(msg)

    unique = table.select("author_raw", "author_uuid").distinct().execute()
    mapping = {
        row["author_raw"]: str(row["author_uuid"])
        for row in unique.to_dict("records")
        if row.get("author_raw")
    }

    sanitized_author = table["author_raw"].substitute(mapping, else_=redact_token)
    anonymized = table.mutate(author_raw=sanitized_author)

    # Also update the 'author' display column if it exists (common in WhatsApp schema)
    if "author" in anonymized.columns:
        anonymized = anonymized.mutate(author=sanitized_author)

    if "text" in anonymized.columns:

        @ibis.udf.scalar.python
        def redact_mentions(message: str | None) -> str | None:
            if message is None:
                return None
            return _sanitize_mentions(message, mapping)

        anonymized = anonymized.mutate(text=redact_mentions(anonymized.text))

    return anonymized
