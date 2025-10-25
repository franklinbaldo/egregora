"""Shared Ibis schema definitions for the content pipeline."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import ibis
import ibis.expr.datatypes as dt
from ibis import udf
from ibis.expr.types import Table

__all__ = ["MESSAGE_SCHEMA", "ensure_message_schema"]

# Default timezone for WhatsApp exports (no timezone in export files)
DEFAULT_TIMEZONE = "UTC"

MESSAGE_SCHEMA: dict[str, dt.DataType] = {
    "timestamp": dt.Timestamp(timezone=DEFAULT_TIMEZONE, scale=9),  # nanosecond precision
    "date": dt.Date(),
    "author": dt.String(),
    "message": dt.String(),
    "original_line": dt.String(),
    "tagged_line": dt.String(),
}


def ensure_message_schema(
    df: Table,
    *,
    timezone: str | ZoneInfo | None = None,
) -> Table:
    """Return ``df`` cast to the canonical :data:`MESSAGE_SCHEMA`.

    The pipeline relies on consistent dtypes so schema validation is performed
    eagerly at ingestion boundaries (parser and render stages). The function is
    intentionally forgiving: missing columns are created and timezone
    normalisation is applied when necessary.
    """

    target_schema = dict(MESSAGE_SCHEMA)

    tz = timezone or DEFAULT_TIMEZONE
    if isinstance(tz, ZoneInfo):
        tz_name = getattr(tz, "key", str(tz))
    else:
        tz_name = str(tz)

    # Update target schema with the desired timezone
    target_schema["timestamp"] = dt.Timestamp(timezone=tz_name, scale=9)

    # Handle empty DataFrame
    if df.count().execute() == 0:
        # Create empty table with correct schema without relying on backend internals
        return ibis.memtable([], schema=ibis.schema(target_schema))

    # Start with the input table
    result = df

    # Cast columns to target types (except timestamp/date which need special handling)
    for name, dtype in target_schema.items():
        if name in {"timestamp", "date"}:
            continue  # Handle separately below

        if name in result.columns:
            # Cast existing column
            result = result.mutate(**{name: result[name].cast(dtype)})
        else:
            # Add missing column with nulls
            result = result.mutate(**{name: ibis.null().cast(dtype)})

    # Handle timestamp column with timezone normalization
    if "timestamp" not in result.columns:
        raise ValueError("DataFrame is missing required 'timestamp' column")

    result = _normalise_timestamp(result, tz_name)
    result = _ensure_date_column(result)

    return result


def _normalise_timestamp(
    table: Table,
    desired_timezone: str,
) -> Table:
    """Normalize timestamp column to desired timezone."""

    # Get current timestamp column
    ts_col = table["timestamp"]

    target_dtype = dt.Timestamp(timezone=desired_timezone, scale=9)

    current_dtype = ts_col.type()
    if isinstance(current_dtype, dt.Timestamp) and current_dtype.timezone is not None:
        normalized_ts = ts_col.cast(target_dtype)
    else:
        tz_literal = ibis.literal(desired_timezone)
        normalized_ts = _localize_to_utc(ts_col, tz_literal).cast(target_dtype)

    return table.mutate(timestamp=normalized_ts)


def _ensure_date_column(table: Table) -> Table:
    """Ensure date column exists, deriving from timestamp if needed."""

    if "date" in table.columns:
        # Cast existing date column
        return table.mutate(date=table["date"].cast(dt.Date()))

    # Derive date from timestamp
    return table.mutate(date=table["timestamp"].date())


@udf.scalar.python
def _localize_to_utc(
    ts: datetime | None, tz_name: str
) -> dt.Timestamp(timezone="UTC"):
    """Attach ``tz_name`` to ``ts`` and convert the instant to UTC."""

    if ts is None:
        return None

    tzinfo = ZoneInfo(tz_name)
    if ts.tzinfo is None:
        localized = ts.replace(tzinfo=tzinfo)
    else:
        localized = ts.astimezone(tzinfo)

    return localized.astimezone(ZoneInfo("UTC"))
