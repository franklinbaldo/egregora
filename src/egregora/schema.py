"""Shared Ibis schema definitions for the content pipeline."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import ibis
import ibis.expr.datatypes as dt
from ibis import udf
from ibis.expr.types import Table

__all__ = ["MESSAGE_SCHEMA", "ensure_message_schema"]

# Default timezone for WhatsApp exports (no timezone in export files)
DEFAULT_TIMEZONE = "UTC"


def _timestamp_dtype(timezone: str | None) -> dt.Timestamp:
    """Return a timestamp datatype with nanosecond precision."""

    return dt.Timestamp(timezone=timezone, scale=9)


def _date_dtype() -> dt.Date:
    """Return a date datatype."""

    return dt.Date()


def _string_dtype() -> dt.String:
    """Return a string datatype."""

    return dt.String()


def _base_message_schema() -> dict[str, dt.DataType]:
    """Base schema shared by all message tables."""

    return {
        "timestamp": _timestamp_dtype(DEFAULT_TIMEZONE),
        "date": _date_dtype(),
        "author": _string_dtype(),
        "message": _string_dtype(),
        "original_line": _string_dtype(),
        "tagged_line": _string_dtype(),
    }


MESSAGE_SCHEMA: dict[str, dt.DataType] = _base_message_schema()


@udf.scalar.builtin(
    name="timezone",
    signature=((dt.string, dt.Timestamp(timezone=None)), dt.Timestamp(timezone="UTC")),
)
def _builtin_timezone(_: str, __: dt.Timestamp) -> dt.Timestamp:  # pragma: no cover - builtin
    """Bind to backend ``timezone`` scalar function.

    The function body is never executed; at runtime Ibis forwards calls to the
    backend implementation. DuckDB mirrors Polars' ``replace_time_zone``
    semantics when a naive timestamp is paired with the export's timezone.
    """
    raise NotImplementedError("ibis replaces builtin bodies at runtime")


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

    target_schema: dict[str, dt.DataType] = dict(MESSAGE_SCHEMA)

    tz = timezone or DEFAULT_TIMEZONE
    if isinstance(tz, ZoneInfo):
        tz_name = getattr(tz, "key", str(tz))
    else:
        tz_name = str(tz)

    # Update target schema with the desired timezone
    target_schema["timestamp"] = _timestamp_dtype(tz_name)

    # Handle empty DataFrame
    if int(df.count().execute()) == 0:
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

    # Determine the current dtype metadata
    schema = table.schema()
    current_dtype = schema.get("timestamp")
    if current_dtype is None:
        raise ValueError("DataFrame is missing required 'timestamp' column")

    desired_dtype = dt.Timestamp(timezone=desired_timezone, scale=9)

    ts_col = table["timestamp"]
    current_timezone: str | None

    if isinstance(current_dtype, dt.Timestamp):
        current_timezone = current_dtype.timezone
        if current_dtype.scale != desired_dtype.scale:
            ts_col = ts_col.cast(dt.Timestamp(timezone=current_timezone, scale=desired_dtype.scale))
    else:
        ts_col = ts_col.cast(dt.Timestamp(scale=desired_dtype.scale))
        current_timezone = None

    if desired_timezone is None:
        normalized_ts = ts_col
    elif current_timezone is None:
        localized = _builtin_timezone(desired_timezone, ts_col.cast(dt.Timestamp()))
        normalized_ts = localized.cast(desired_dtype)
    elif current_timezone == desired_timezone:
        normalized_ts = ts_col
    else:
        normalized_ts = ts_col.cast(desired_dtype)

    return table.mutate(timestamp=normalized_ts)


def _ensure_date_column(table: Table) -> Table:
    """Ensure date column exists, deriving from timestamp if needed."""

    if "date" in table.columns:
        # Cast existing date column
        return table.mutate(date=table["date"].cast(dt.Date()))

    # Derive date from timestamp
    return table.mutate(date=table["timestamp"].date())
