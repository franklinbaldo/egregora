"""Augmentation stage - Enrich data with context and metadata.

This package handles optional data enrichment:
- Media extraction and processing
- URL and media enrichment via LLM
- Profile generation for active authors
"""

from . import enrichment
from .profiler import create_or_update_profile, filter_opted_out_authors, get_active_authors

__all__ = [
    "enrichment",
    "create_or_update_profile",
    "get_active_authors",
    "filter_opted_out_authors",
]
