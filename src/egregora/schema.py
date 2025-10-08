"""Shared Polars schema definitions for the content pipeline."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import polars as pl
from polars.datatypes import Datetime as DateTimeType

from .config import DEFAULT_TIMEZONE

__all__ = ["MESSAGE_SCHEMA", "ensure_message_schema"]

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

    casts = {name: dtype for name, dtype in MESSAGE_SCHEMA.items()}
    if df.is_empty():
        return pl.DataFrame(schema=casts)

    tz = timezone or DEFAULT_TIMEZONE
    if isinstance(tz, ZoneInfo):
        tz_name = getattr(tz, "key", str(tz))
    else:
        tz_name = str(tz)

    frame = df.cast(casts, strict=False)

    timestamp_dtype = frame.schema.get("timestamp")
    if timestamp_dtype is None:
        raise ValueError("DataFrame is missing required 'timestamp' column")

    desired_dtype = pl.Datetime(time_unit="ns", time_zone=tz_name)
    if timestamp_dtype == desired_dtype:
        timestamp_expr = pl.col("timestamp")
    elif isinstance(timestamp_dtype, DateTimeType):
        if timestamp_dtype.time_zone is None:
            timestamp_expr = (
                pl.col("timestamp")
                .cast(pl.Datetime(time_unit="ns"))
                .dt.replace_time_zone(tz_name)
            )
        else:
            timestamp_expr = pl.col("timestamp").dt.convert_time_zone(tz_name)
    else:
        timestamp_expr = (
            pl.col("timestamp").str.strptime(pl.Datetime(time_unit="ns"))
            .dt.replace_time_zone(tz_name)
        )

    frame = frame.with_columns(timestamp_expr.alias("timestamp"))

    if "date" in frame.columns:
        frame = frame.with_columns(pl.col("date").cast(pl.Date).alias("date"))
    else:
        frame = frame.with_columns(pl.col("timestamp").dt.date().alias("date"))

    for name in ("author", "message", "original_line", "tagged_line"):
        if name not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=pl.String).alias(name))
        else:
            frame = frame.with_columns(pl.col(name).cast(pl.String).alias(name))

    return frame
