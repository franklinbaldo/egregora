"""Convert DataFrames back to text transcripts for newsletter generation."""

from datetime import date
import pandas as pd
import logging

from .models import GroupSource
from .parser import parse_multiple
from .merger import merge_with_tags

logger = logging.getLogger(__name__)


def extract_transcript(source: GroupSource, target_date: date) -> str:
    """
    Extract transcript for a specific date.
    Works for both real AND virtual groups!
    """
    
    if source.is_virtual:
        # Virtual: merge with tags
        df = merge_with_tags(source.exports, source.merge_config)
        
        # Filter date
        df_day = df[df['date'] == target_date]
        
        if df_day.empty:
            return ""
        
        # Return tagged lines
        return '\n'.join(df_day['tagged_line'].tolist())
    
    else:
        # Real: parse simply
        exports_for_date = [e for e in source.exports if e.export_date == target_date]
        
        if not exports_for_date:
            return ""
        
        df = parse_multiple(exports_for_date)
        
        if df.empty:
            return ""
        
        # Return original lines
        return '\n'.join(df['original_line'].tolist())


def get_stats_for_date(source: GroupSource, target_date: date) -> dict:
    """Statistics for a specific day."""
    
    if source.is_virtual:
        df = merge_with_tags(source.exports, source.merge_config)
    else:
        df = parse_multiple(source.exports)
    
    df_day = df[df['date'] == target_date]
    
    if df_day.empty:
        return {}
    
    return {
        'message_count': len(df_day),
        'participant_count': df_day['author'].nunique(),
        'first_message': df_day['timestamp'].min(),
        'last_message': df_day['timestamp'].max(),
    }


def get_available_dates(source: GroupSource) -> list[date]:
    """Get all available dates for a source."""
    
    if source.is_virtual:
        df = merge_with_tags(source.exports, source.merge_config)
    else:
        df = parse_multiple(source.exports)
    
    if df.empty:
        return []
    
    return sorted(df['date'].unique())