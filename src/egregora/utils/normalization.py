"""Timezone and schema normalization utilities.

This module provides canonical entry points for normalizing data
as it enters the pipeline, ensuring all downstream stages can rely
on consistent timestamps and schemas.
"""

from ibis.expr.types import Table

from ..core.schema import ensure_message_schema as _ensure_message_schema


def normalize_timestamps(table: Table, timezone: str = "UTC") -> Table:
    """
    Normalize all timestamp columns to UTC with scale-9 precision.

    This is the canonical entry point for timezone handling.
    All downstream stages assume UTC timestamps with nanosecond precision.

    Args:
        table: Input table with timestamp column
        timezone: Timezone to interpret naive timestamps (default: UTC)

    Returns:
        Table with normalized timestamps in UTC

    Example:
        >>> # At pipeline entry point (after ingestion)
        >>> conversations = normalize_timestamps(conversations, timezone="UTC")
        >>> # Now all downstream code can assume UTC timestamps
    """
    return _ensure_message_schema(table, timezone=timezone)


def ensure_schema_compliance(table: Table, timezone: str = "UTC") -> Table:
    """
    Ensure table conforms to MESSAGE_SCHEMA.

    Alias for normalize_timestamps - both functions do the same thing.
    Use whichever name better expresses intent in your code.

    Args:
        table: Input table
        timezone: Timezone for timestamp interpretation

    Returns:
        Table conforming to MESSAGE_SCHEMA
    """
    return normalize_timestamps(table, timezone=timezone)
