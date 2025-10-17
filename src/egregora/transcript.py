"""Convert DataFrames back to text transcripts for post generation."""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from datetime import date

import polars as pl

from .merger import merge_with_tags
from .models import GroupSource
from .parser import parse_multiple
from .schema import ensure_message_schema

logger = logging.getLogger(__name__)


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

    render_expr = _build_render_expression(frame, use_tagged=use_tagged, prefer_original_line=prefer_original_line)
    frame = frame.with_columns(render_expr.alias("__render_line"))

    lines = [line or "" for line in frame.get_column("__render_line").to_list()]
    return "\n".join(lines)


def _build_render_expression(
    frame: pl.DataFrame,
    *,
    use_tagged: bool,
    prefer_original_line: bool,
) -> pl.Expr:
    """Return a ``pl.Expr`` that yields the best textual line per message."""

    def _non_empty(column: str) -> pl.Expr:
        return (
            pl.when(pl.col(column).is_not_null() & (pl.col(column).str.len_chars() > 0))
            .then(pl.col(column))
            .otherwise(None)
        )

    candidates: list[pl.Expr] = []

    if use_tagged and "tagged_line" in frame.columns:
        candidates.append(_non_empty("tagged_line"))

    if prefer_original_line and "original_line" in frame.columns:
        candidates.append(_non_empty("original_line"))

    time_expr = (
        pl.when(pl.col("time").is_not_null())
        .then(pl.col("time"))
        .otherwise(pl.col("timestamp").dt.strftime("%H:%M"))
    )
    author_expr = pl.col("author").fill_null("")
    message_expr = pl.col("message").fill_null("")
    fallback = pl.format("{} — {}: {}", time_expr, author_expr, message_expr)

    # If the caller did not request tagged/original data or the columns are absent,
    # fall back automatically to whichever rich column exists.
    if not candidates:
        for column_name in ("tagged_line", "original_line"):
            if column_name in frame.columns:
                candidates.append(_non_empty(column_name))

    candidates.append(fallback)
    return pl.coalesce(*candidates)


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
        _DATAFRAME_CACHE.set(key, df)
    return df.clone()


def _build_cache_key(source: GroupSource) -> str:
    """Return a stable hashed cache key for ``source``."""

    hasher = hashlib.sha256()
    hasher.update(b"is_virtual=" + str(int(source.is_virtual)).encode())

    for export in sorted(source.exports, key=lambda exp: (str(exp.zip_path), exp.chat_file)):
        hasher.update(b"|export=")
        hasher.update(str(export.zip_path.resolve()).encode())
        hasher.update(b"|chat=" + export.chat_file.encode())
        hasher.update(b"|date=" + export.export_date.isoformat().encode())

    if source.is_virtual and source.merge_config:
        merge = source.merge_config
        hasher.update(b"|merge.tag_style=" + merge.tag_style.encode())
        if merge.model_override:
            hasher.update(b"|merge.model=" + merge.model_override.encode())
        for slug, emoji in sorted(merge.group_emojis.items()):
            hasher.update(b"|merge.emoji=" + str(slug).encode() + b":" + emoji.encode())
        if hasattr(merge, "default_emoji") and merge.default_emoji:
            hasher.update(b"|merge.default_emoji=" + merge.default_emoji.encode())

    return hasher.hexdigest()


class _LRUDataFrameCache:
    """Simple LRU cache for Polars DataFrames with copy-on-read semantics."""

    def __init__(self, max_entries: int = 16) -> None:
        self._max_entries = max(1, int(max_entries))
        self._store: OrderedDict[str, pl.DataFrame] = OrderedDict()

    def get(self, key: str) -> pl.DataFrame | None:
        cached = self._store.get(key)
        if cached is None:
            return None
        self._store.move_to_end(key)
        return cached

    def set(self, key: str, value: pl.DataFrame) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


_DATAFRAME_CACHE = _LRUDataFrameCache(max_entries=32)


__all__ = [
    "render_transcript",
    "get_stats_for_date",
    "get_available_dates",
    "load_source_dataframe",
]
