"""Convert DataFrames back to text transcripts for post generation."""

from __future__ import annotations

import logging
from datetime import date

import polars as pl

from .merger import merge_with_tags
from .models import GroupSource
from .parser import parse_multiple
from .schema import ensure_message_schema

logger = logging.getLogger(__name__)

#TODO: The logic for choosing which column to use for rendering the transcript is a bit complex. It could be simplified.
def render_transcript(
    df: pl.DataFrame,
    *,
    use_tagged: bool = False,
    prefer_original_line: bool = False,
) -> str:
    """Render a Polars frame into the canonical transcript text."""

    frame = ensure_message_schema(df)
    if frame.is_empty():
        return ""

    frame = frame.sort("timestamp")

    if "time" not in frame.columns:
        frame = frame.with_columns(pl.col("timestamp").dt.strftime("%H:%M").alias("time"))

    time_expr = (
        pl.when(pl.col("time").is_not_null())
        .then(pl.col("time"))
        .otherwise(pl.col("timestamp").dt.strftime("%H:%M"))
    )
    author_expr = pl.col("author").fill_null("")
    message_expr = pl.col("message").fill_null("")
    fallback = pl.format("{} — {}: {}", time_expr, author_expr, message_expr)

    candidates: list[pl.Expr] = []

    if use_tagged and "tagged_line" in frame.columns:
        candidates.append(
            pl.when(
                pl.col("tagged_line").is_not_null() & (pl.col("tagged_line").str.len_chars() > 0)
            )
            .then(pl.col("tagged_line"))
            .otherwise(None)
        )

    if prefer_original_line and "original_line" in frame.columns:
        candidates.append(
            pl.when(
                pl.col("original_line").is_not_null()
                & (pl.col("original_line").str.len_chars() > 0)
            )
            .then(pl.col("original_line"))
            .otherwise(None)
        )

    candidates.append(fallback)

    frame = frame.with_columns(pl.coalesce(*candidates).alias("__render_line"))

    lines = [line or "" for line in frame.get_column("__render_line").to_list()]
    return "\n".join(lines)


def get_stats_for_date(source: GroupSource, target_date: date) -> dict:
    """Statistics for a specific day."""

    df = load_source_dataframe(source)
    df_day = df.filter(pl.col("date") == target_date)

    if df_day.is_empty():
        return {}

    author_series = df_day.get_column("author")
    timestamp_series = df_day.get_column("timestamp")

    return {
        "message_count": df_day.height,
        "participant_count": author_series.n_unique(),
        "first_message": timestamp_series.min(),
        "last_message": timestamp_series.max(),
    }


def get_available_dates(source: GroupSource) -> list[date]:
    """Get all available dates for a source."""

    df = load_source_dataframe(source)
    if df.is_empty():
        return []

    dates = df.get_column("date").to_list()
    return sorted({d for d in dates})


def load_source_dataframe(source: GroupSource) -> pl.DataFrame:
    key = _build_cache_key(source)
    cached = _DATAFRAME_CACHE.get(key)
    if cached is not None:
        return cached.clone()

    if source.is_virtual:
        if not source.merge_config:
            raise ValueError(f"Virtual source '{source.slug}' is missing merge configuration")
        df = merge_with_tags(source.exports, source.merge_config)
    else:
        df = parse_multiple(source.exports)

    df = ensure_message_schema(df)

    if not df.is_empty():
        _DATAFRAME_CACHE[key] = df
    return df.clone()

# TODO: The cache key is a tuple of many items. It could be simplified by using a
# hash of the items. This would be more memory-efficient and robust to changes
# in the MergeConfig class.
def _build_cache_key(source: GroupSource) -> tuple:
    exports_key = tuple(
        sorted(
            (
                str(exp.zip_path.resolve()),
                exp.chat_file,
                exp.export_date.isoformat(),
            )
            for exp in source.exports
        )
    )

    if source.is_virtual and source.merge_config:
        merge = source.merge_config
        merge_key = (
            merge.tag_style,
            merge.model_override,
            tuple(sorted(merge.group_emojis.items())),
        )
    else:
        merge_key = None

    return (source.is_virtual, exports_key, merge_key)

# FIXME: This is a global in-memory cache. It might grow indefinitely and cause
# memory issues. A proper cache implementation with a size limit, like
# `diskcache.Cache` or a simple LRU cache from `functools`, should be used.
_DATAFRAME_CACHE: dict[tuple, pl.DataFrame] = {}


__all__ = [
    "render_transcript",
    "get_stats_for_date",
    "get_available_dates",
    "load_source_dataframe",
]
