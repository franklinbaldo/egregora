"""Convert DataFrames back to text transcripts for newsletter generation."""

from __future__ import annotations

from datetime import date
import logging

import polars as pl

from .models import GroupSource
from .parser import parse_multiple
from .merger import merge_with_tags

logger = logging.getLogger(__name__)


def render_transcript(df_day: pl.DataFrame, *, use_tagged: bool) -> str:
    """Render a text transcript from a daily DataFrame."""
    if df_day.is_empty():
        return ""

    column = (
        "tagged_line"
        if use_tagged and "tagged_line" in df_day.columns
        else "original_line"
    )
    if column not in df_day.columns:
        # Fallback for older dataframes that might not have original_line
        return "\n".join(
            df_day.select(
                pl.concat_str(
                    [pl.col("time"), pl.col("author"), pl.col("message")],
                    separator=" - ",
                )
            )
            .to_series()
            .to_list()
        )

    return "\n".join(df_day.get_column(column).to_list())


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

    if not df.is_empty():
        _DATAFRAME_CACHE[key] = df
    return df.clone()


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


_DATAFRAME_CACHE: dict[tuple, pl.DataFrame] = {}


__all__ = [
    "render_transcript",
    "get_available_dates",
    "load_source_dataframe",
]
