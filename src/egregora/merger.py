"""Merging multiple DataFrames with group tags for virtual groups."""

import pandas as pd
from typing import Literal
import logging

from .models import WhatsAppExport, MergeConfig, GroupSource
from .parser import parse_multiple

logger = logging.getLogger(__name__)


def create_virtual_groups(
    real_groups: dict[str, list[WhatsAppExport]],
    merge_configs: dict[str, MergeConfig],
) -> dict[str, GroupSource]:
    """Create virtual groups from merge configurations."""
    
    virtual = {}
    
    for slug, config in merge_configs.items():
        # Collect exports from source groups
        merged_exports = []
        
        for source_slug in config.source_groups:
            exports = real_groups.get(source_slug, [])
            if not exports:
                logger.warning(f"Virtual group '{slug}': source '{source_slug}' not found")
                continue
            merged_exports.extend(exports)
        
        if not merged_exports:
            logger.warning(f"Virtual group '{slug}': no valid source groups found")
            continue
        
        # Sort by date
        merged_exports.sort(key=lambda e: e.export_date)
        
        virtual[slug] = GroupSource(
            slug=slug,
            name=config.name,
            exports=merged_exports,
            is_virtual=True,
            merge_config=config,
        )
        
        logger.info(f"Created virtual group '{config.name}' ({slug}) from {len(config.source_groups)} sources")
    
    return virtual


def merge_with_tags(
    exports: list[WhatsAppExport],
    merge_config: MergeConfig,
) -> pd.DataFrame:
    """
    Merge exports into single DataFrame with tags.
    
    Returns:
        DataFrame with additional 'tagged_line' column
    """
    
    # Parse all
    df = parse_multiple(exports)
    
    if df.empty:
        return df
    
    # Add tagged_line
    df['tagged_line'] = df.apply(
        lambda row: _add_tag(
            row['time'],
            row['author'],
            row['message'],
            row['group_slug'],
            row['group_name'],
            merge_config,
        ),
        axis=1
    )
    
    return df


def _add_tag(
    time: str,
    author: str,
    message: str,
    group_slug: str,
    group_name: str,
    config: MergeConfig,
) -> str:
    """Add group tag to message."""
    
    if config.tag_style == "emoji":
        emoji = config.group_emojis.get(group_slug, "📱")
        return f"{time} — {author} {emoji}: {message}"
    
    elif config.tag_style == "prefix":
        return f"{time} — [{group_name}] {author}: {message}"
    
    else:  # brackets
        return f"{time} — {author} [{group_name}]: {message}"


def get_merge_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Statistics of merge by group."""
    
    if df.empty:
        return pd.DataFrame()
    
    return (
        df.groupby(['group_slug', 'group_name'])
        .size()
        .reset_index(name='message_count')
        .sort_values('message_count', ascending=False)
    )