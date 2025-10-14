"""Merging multiple DataFrames with group tags for virtual groups."""

from __future__ import annotations

import logging

import polars as pl

from .models import GroupSource, MergeConfig, WhatsAppExport
from .parser import parse_multiple
from .types import GroupSlug

logger = logging.getLogger(__name__)


def create_virtual_groups(
    real_groups: dict[GroupSlug, list[WhatsAppExport]],
    merge_configs: dict[GroupSlug, MergeConfig],
) -> dict[GroupSlug, GroupSource]:
    """Create virtual groups from merge configurations."""

    virtual: dict[GroupSlug, GroupSource] = {}

    for slug, config in merge_configs.items():
        merged_exports: list[WhatsAppExport] = []

        for source_slug in config.source_groups:
            exports = real_groups.get(source_slug, [])
            if not exports:
                logger.warning("Virtual group '%s': source '%s' not found", slug, source_slug)
                continue
            merged_exports.extend(exports)

        if not merged_exports:
            logger.warning("Virtual group '%s': no valid source groups found", slug)
            continue

        merged_exports.sort(key=lambda e: e.export_date)

        virtual[slug] = GroupSource(
            slug=slug,
            name=config.name,
            exports=merged_exports,
            is_virtual=True,
            merge_config=config,
        )

        logger.info(
            "Created virtual group '%s' (%s) from %d sources",
            config.name,
            slug,
            len(config.source_groups),
        )

    return virtual


def merge_with_tags(
    exports: list[WhatsAppExport],
    merge_config: MergeConfig,
) -> pl.DataFrame:
    """Merge exports into a single ``DataFrame`` with tagged lines."""

    df = parse_multiple(exports)

    if df.is_empty():
        return df

    if merge_config.tag_style == "emoji":
        emoji_expr = pl.col("group_slug").replace(
            merge_config.group_emojis,
            default="📱",
        )
        tagged = pl.format(
            "{} — {} {}: {}",
            pl.col("time"),
            pl.col("anon_author"),
            emoji_expr,
            pl.col("message"),
        )
    elif merge_config.tag_style == "prefix":
        tagged = pl.format(
            "{} — [{}] {}: {}",
            pl.col("time"),
            pl.col("group_name"),
            pl.col("anon_author"),
            pl.col("message"),
        )
    else:  # brackets
        tagged = pl.format(
            "{} — {} [{}]: {}",
            pl.col("time"),
            pl.col("anon_author"),
            pl.col("group_name"),
            pl.col("message"),
        )

    return df.with_columns(tagged.alias("tagged_line"))


def get_merge_stats(df: pl.DataFrame) -> pl.DataFrame:
    """Statistics of merge by group."""

    if df.is_empty():
        return pl.DataFrame(
            {
                "group_slug": pl.Series(dtype=pl.Utf8, values=[]),
                "group_name": pl.Series(dtype=pl.Utf8, values=[]),
                "message_count": pl.Series(dtype=pl.Int64, values=[]),
            }
        )

    return (
        df.group_by("group_slug", "group_name")
        .agg(pl.len().alias("message_count"))
        .sort("message_count", descending=True)
    )


__all__ = [
    "create_virtual_groups",
    "merge_with_tags",
    "get_merge_stats",
]
