"""Core data structures - Shared models, schemas, and types.

This package contains domain models and data structures used across
all pipeline stages.
"""

from . import database_schema
from .models import GroupSource, MergeConfig, WhatsAppExport
from .schema import MESSAGE_SCHEMA, WHATSAPP_SCHEMA
from .types import GroupSlug, PostSlug

__all__ = [
    # Models
    "WhatsAppExport",
    "GroupSource",
    "MergeConfig",
    # Schemas (Data)
    "WHATSAPP_SCHEMA",
    "MESSAGE_SCHEMA",
    # Schemas (Database)
    "database_schema",
    # Types
    "GroupSlug",
    "PostSlug",
]
