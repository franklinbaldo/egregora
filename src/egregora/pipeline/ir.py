"""Intermediate Representation (IR) for source-agnostic pipeline.

This module defines the standardized data format that all source adapters
must produce. The IR schema ensures consistency across different sources
(WhatsApp, Slack, Discord, etc.) and enables the core pipeline to process
messages from any source without modification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import ibis.expr.datatypes as dt

from egregora.schema import DEFAULT_TIMEZONE, ensure_message_schema

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from ibis.expr.types import Table

__all__ = [
    "IR_SCHEMA",
    "create_ir_table",
    "validate_ir_schema",
]


# Intermediate Representation Schema
# This is the contract that all source adapters must fulfill
IR_SCHEMA: dict[str, dt.DataType] = {
    # Core message fields (required by all sources)
    "timestamp": dt.Timestamp(timezone=DEFAULT_TIMEZONE, scale=9),  # nanosecond precision
    "date": dt.Date(),  # derived from timestamp
    "author": dt.String(),  # anonymized or pseudonymized author identifier
    "message": dt.String(),  # message content/body
    # Metadata fields (for debugging and processing tracking)
    "original_line": dt.String(),  # original raw line from source (for debugging)
    "tagged_line": dt.String(),  # processing tracking field
    # Identifiers
    "message_id": dt.String(nullable=True),  # deterministic message ID
}


def validate_ir_schema(table: Table) -> tuple[bool, list[str]]:
    """Validate that a table conforms to the IR schema contract.

    Args:
        table: Ibis table to validate

    Returns:
        Tuple of (is_valid, list_of_errors)

    Example:
        >>> is_valid, errors = validate_ir_schema(messages_table)
        >>> if not is_valid:
        ...     raise ValueError(f"IR schema validation failed: {errors}")

    """
    errors = []
    schema = table.schema()

    # Check for missing required columns
    for col_name, expected_dtype in IR_SCHEMA.items():
        if col_name not in schema:
            errors.append(f"Missing required column: {col_name}")
            continue

        # Check column type compatibility (allow some flexibility for nullability)
        actual_dtype = schema[col_name]
        if not _is_dtype_compatible(actual_dtype, expected_dtype):
            errors.append(
                f"Column '{col_name}' has incompatible type. Expected: {expected_dtype}, Got: {actual_dtype}"
            )

    return len(errors) == 0, errors


def _is_dtype_compatible(actual: dt.DataType, expected: dt.DataType) -> bool:
    """Check if two dtypes are compatible (accounting for nullability)."""
    # For basic comparison, check the dtype class
    if type(actual) != type(expected):
        return False

    # For Timestamp, also check timezone compatibility
    if isinstance(actual, dt.Timestamp) and isinstance(expected, dt.Timestamp):
        # Allow any timezone, but both must have or not have timezone
        actual_has_tz = actual.timezone is not None
        expected_has_tz = expected.timezone is not None
        return actual_has_tz == expected_has_tz

    return True


def create_ir_table(
    table: Table,
    *,
    timezone: str | ZoneInfo | None = None,
) -> Table:
    """Convert a table to conform to IR schema, adding/casting fields as needed.

    This function ensures strict compliance with the IR_SCHEMA by:
    - Adding missing columns with null values
    - Casting existing columns to correct types
    - Dropping extra columns not in IR_SCHEMA
    - Normalizing timezone information

    Args:
        table: Source table with at minimum: timestamp, author, message
        timezone: Timezone for timestamp normalization

    Returns:
        Table conforming to IR_SCHEMA

    Raises:
        ValueError: If table is missing required core fields (timestamp, author, message)

    Example:
        >>> raw_table = parse_raw_export(...)
        >>> ir_table = create_ir_table(raw_table, timezone="America/New_York")

    """
    # Delegate to existing schema enforcement logic
    # This reuses the battle-tested ensure_message_schema function
    return ensure_message_schema(table, timezone=timezone)
