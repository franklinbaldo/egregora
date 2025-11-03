"""Augmentation stage - Enrich data with context and metadata.

This package handles optional data enrichment:
- Media extraction and processing
- URL and media enrichment via LLM
- Profile generation for active authors
"""

from . import enrichment
from .profiler import (
    apply_command_to_profile,
    filter_opted_out_authors,
    get_active_authors,
    read_profile,
    write_profile,
)

__all__ = [
    "enrichment",
    "apply_command_to_profile",
    "get_active_authors",
    "filter_opted_out_authors",
    "read_profile",
    "write_profile",
]
