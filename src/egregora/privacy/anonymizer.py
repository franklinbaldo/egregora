"""Privacy-preserving anonymization utilities for IR tables."""

from __future__ import annotations

import re

import ibis
from ibis.expr.types import Table

from egregora.constants import MentionPrivacyStrategy

DEFAULT_REDACTED = "[redacted]"
MENTION_PATTERN = re.compile("\\u2068(?P<name>.*?)\\u2069")


def _get_author_mapping(table: Table) -> dict[str, str]:
    """Extract mapping from author_raw to author_uuid from table."""
    required = {"author_raw", "author_uuid"}
    missing = required - set(table.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        msg = f"Table is missing required columns for anonymization: {missing_cols}"
        raise ValueError(msg)

    unique = table.select("author_raw", "author_uuid").distinct().execute()
    return {
        row["author_raw"]: str(row["author_uuid"])
        for row in unique.to_dict("records")
        if row.get("author_raw")
    }


def _sanitize_mentions(
    text: str,
    mapping: dict[str, str] | None,
    strategy: MentionPrivacyStrategy,
    redact_token: str = DEFAULT_REDACTED,
) -> str:
    if not text or "\u2068" not in text:
        return text

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")

        if strategy == MentionPrivacyStrategy.NONE:
            return f"\u2068{name}\u2069"

        if strategy == MentionPrivacyStrategy.UUID_REPLACEMENT:
            if mapping:
                replacement = mapping.get(name)
                if replacement:
                    return f"@{replacement}"
            # Fallback to redaction if mapping fails or not provided
            return redact_token

        if strategy == MentionPrivacyStrategy.GENERIC_REDACTION:
            return "@[MENTION]"

        if strategy == MentionPrivacyStrategy.ROLE_BASED:
            # Not implemented yet, fall back to generic
            return "@[Participant]"

        return redact_token

    return MENTION_PATTERN.sub(replace, text)


def anonymize_mentions(
    table: Table,
    strategy: MentionPrivacyStrategy,
    mapping: dict[str, str] | None = None,
) -> Table:
    """Apply privacy strategy to mentions in text column.

    Args:
        table: Input table
        strategy: Mention privacy strategy
        mapping: Optional author mapping (name -> uuid) for UUID replacement

    Returns:
        Table with mentions processed

    """
    if "text" not in table.columns:
        return table

    if strategy == MentionPrivacyStrategy.NONE:
        return table

    if strategy == MentionPrivacyStrategy.UUID_REPLACEMENT and mapping is None:
        # Try to extract mapping if possible
        try:
            mapping = _get_author_mapping(table)
        except ValueError:
            pass

    @ibis.udf.scalar.python
    def process_mentions(message: str) -> str:
        if message is None:
            return None
        return _sanitize_mentions(message, mapping, strategy)

    return table.mutate(text=process_mentions(table.text))


def anonymize_table(
    table: Table,
    *,
    redact_token: str = DEFAULT_REDACTED,
    enabled: bool = True,
    process_mentions: bool = True,  # Default True for safety/backward compatibility
) -> Table:
    """Redact author_raw values while preserving deterministic author_uuid.

    Args:
        table: Input table with author_raw and author_uuid columns
        redact_token: Token to use for redacted values
        enabled: If False, skip anonymization and return table as-is
        process_mentions: Whether to also process mentions using default logic

    Returns:
        Table with author_raw anonymized (if enabled)

    """
    # If anonymization is disabled, return table unchanged
    if not enabled:
        return table

    mapping = _get_author_mapping(table)

    sanitized_author = table["author_raw"].substitute(mapping, else_=redact_token)
    anonymized = table.mutate(author_raw=sanitized_author)

    # Also update the 'author' display column if it exists (common in WhatsApp schema)
    if "author" in anonymized.columns:
        anonymized = anonymized.mutate(author=sanitized_author)

    if process_mentions and "text" in anonymized.columns:
        # Legacy behavior: uses UUID replacement logic implicitly
        @ibis.udf.scalar.python
        def redact_mentions(message: str) -> str:
            if message is None:
                return None
            return _sanitize_mentions(message, mapping, MentionPrivacyStrategy.UUID_REPLACEMENT, redact_token)

        anonymized = anonymized.mutate(text=redact_mentions(anonymized.text))

    return anonymized
