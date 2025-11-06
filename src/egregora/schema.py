"""Shared Ibis schema definitions for the content pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import ibis
import ibis.expr.datatypes as dt
from ibis import udf

from egregora.types import GroupSlug

if TYPE_CHECKING:
    from ibis.expr.types import Table
__all__ = ["MESSAGE_SCHEMA", "WHATSAPP_SCHEMA", "ensure_message_schema", "group_slug"]
DEFAULT_TIMEZONE = "UTC"
MESSAGE_SCHEMA: dict[str, dt.DataType] = {
    "timestamp": dt.Timestamp(timezone=DEFAULT_TIMEZONE, scale=9),
    "date": dt.Date(),
    "author": dt.String(),
    "message": dt.String(),
    "original_line": dt.String(),
    "tagged_line": dt.String(),
    "message_id": dt.String(nullable=True),
}
WHATSAPP_SCHEMA = MESSAGE_SCHEMA


def group_slug(group_name: str) -> GroupSlug:
    """Create a URL-safe slug from a group name.

    Args:
        group_name: The display name of the group

    Returns:
        A URL-safe slug suitable for use in file paths and URLs

    """
    return GroupSlug(group_name.lower().replace(" ", "-"))


@udf.scalar.builtin(
    name="timezone", signature=((dt.string, dt.Timestamp(timezone=None)), dt.Timestamp(timezone="UTC"))
)
def _builtin_timezone(_: str, __: dt.Timestamp) -> dt.Timestamp:
    """Bind to backend ``timezone`` scalar function.

    The function body is never executed; at runtime Ibis forwards calls to the
    backend implementation. DuckDB mirrors Polars' ``replace_time_zone``
    semantics when a naive timestamp is paired with the export's timezone.
    """


def ensure_message_schema(table: Table, *, timezone: str | ZoneInfo | None = None) -> Table:
    """Return ``table`` cast to the canonical :data:`MESSAGE_SCHEMA`.

    The pipeline relies on consistent dtypes so schema validation is performed
    eagerly at ingestion boundaries (parser and render stages). This function
    strictly enforces MESSAGE_SCHEMA by:
    - Adding missing columns with nulls
    - Casting existing columns to correct types
    - Dropping any extra columns not in MESSAGE_SCHEMA
    - Normalizing timezone information
    """
    target_schema = dict(MESSAGE_SCHEMA)
    tz = timezone or DEFAULT_TIMEZONE
    tz_name = getattr(tz, "key", str(tz)) if isinstance(tz, ZoneInfo) else str(tz)
    target_schema["timestamp"] = dt.Timestamp(timezone=tz_name, scale=9)
    if int(table.count().execute()) == 0:
        return ibis.memtable([], schema=ibis.schema(target_schema))
    result = table
    for name, dtype in target_schema.items():
        if name in {"timestamp", "date"}:
            continue
        if name in result.columns:
            result = result.mutate(**{name: result[name].cast(dtype)})
        else:
            result = result.mutate(**{name: ibis.null().cast(dtype)})
    if "timestamp" not in result.columns:
        msg = "Table is missing required 'timestamp' column"
        raise ValueError(msg)
    result = _normalise_timestamp(result, tz_name)
    result = _ensure_date_column(result)
    extra_columns = set(result.columns) - set(target_schema.keys())
    if extra_columns:
        result = result.select(*target_schema.keys())
    return result


def _normalise_timestamp(table: Table, desired_timezone: str) -> Table:
    """Normalize timestamp column to desired timezone."""
    schema = table.schema()
    current_dtype = schema.get("timestamp")
    if current_dtype is None:
        msg = "Table is missing required 'timestamp' column"
        raise ValueError(msg)
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
        return table.mutate(date=table["date"].cast(dt.Date()))
    return table.mutate(date=table["timestamp"].date())
