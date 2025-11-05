"""Core data structures - Shared models, schemas, and types.

This package contains domain models and data structures used across
all pipeline stages.
"""

from . import database_schema
from .models import GroupSource, MergeConfig, WhatsAppExport
from .types import GroupSlug, PostSlug

__all__ = [
    # Models
    "WhatsAppExport",
    "GroupSource",
    "MergeConfig",
    # Schemas (Database)
    "database_schema",
    # Types
    "GroupSlug",
    "PostSlug",
]
