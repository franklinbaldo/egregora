"""Shared Polars schema definitions for the content pipeline."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import polars as pl
from polars.datatypes import Datetime as DateTimeType

__all__ = ["MESSAGE_SCHEMA", "ensure_message_schema"]

# Default timezone for WhatsApp exports (no timezone in export files)
DEFAULT_TIMEZONE = "UTC"

MESSAGE_SCHEMA: dict[str, pl.DataType] = {
    "timestamp": pl.Datetime(time_unit="ns", time_zone=DEFAULT_TIMEZONE),
    "date": pl.Date,
    "author": pl.String,
    "message": pl.String,
    "original_line": pl.String,
    "tagged_line": pl.String,
}


def ensure_message_schema(
    df: pl.DataFrame,
    *,
    timezone: str | ZoneInfo | None = None,
) -> pl.DataFrame:
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

    desired_dtype = pl.Datetime(time_unit="ns", time_zone=tz_name)
    target_schema["timestamp"] = desired_dtype

    if df.is_empty():
        return pl.DataFrame(schema=target_schema)

    casts = {
        name: dtype
        for name, dtype in target_schema.items()
        if name != "timestamp" and name in df.columns
    }

    frame = df.cast(casts, strict=False) if casts else df.clone()

    frame = frame.with_columns(_normalise_timestamp(frame, desired_dtype))
    frame = _ensure_date_column(frame)
    frame = _ensure_text_columns(frame, ("author", "message", "original_line", "tagged_line"))
    return frame


def _normalise_timestamp(
    frame: pl.DataFrame,
    desired_dtype: pl.Datetime,
) -> pl.Expr:
    """Return a ``pl.Expr`` that yields a timestamp in the desired dtype."""

    tz_name = desired_dtype.time_zone
    if tz_name is None:
        raise ValueError("desired_dtype must have a timezone")

    timestamp_dtype = frame.schema.get("timestamp")
    if timestamp_dtype is None:
        raise ValueError("DataFrame is missing required 'timestamp' column")

    if timestamp_dtype == desired_dtype:
        return pl.col("timestamp")

    if isinstance(timestamp_dtype, DateTimeType):
        expr = pl.col("timestamp").dt.cast_time_unit(desired_dtype.time_unit)
        if timestamp_dtype.time_zone is None:
            return expr.dt.replace_time_zone(tz_name)
        return expr.dt.convert_time_zone(tz_name)

    return (
        pl.col("timestamp")
        .str.strptime(pl.Datetime(time_unit=desired_dtype.time_unit))
        .dt.replace_time_zone(tz_name)
    )


def _ensure_date_column(frame: pl.DataFrame) -> pl.DataFrame:
    if "date" in frame.columns:
        return frame.with_columns(pl.col("date").cast(pl.Date).alias("date"))
    return frame.with_columns(pl.col("timestamp").dt.date().alias("date"))


def _ensure_text_columns(frame: pl.DataFrame, columns: tuple[str, ...]) -> pl.DataFrame:
    for name in columns:
        if name in frame.columns:
            frame = frame.with_columns(pl.col(name).cast(pl.String).alias(name))
        else:
            frame = frame.with_columns(pl.lit(None, dtype=pl.String).alias(name))
    return frame
