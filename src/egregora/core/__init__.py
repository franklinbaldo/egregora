"""Core data structures - Shared models, schemas, and types.

This package contains domain models and data structures used across
all pipeline stages.
"""

from . import database_schema
from .input_source import InputMetadata, InputSource, input_registry
from .models import GroupSource, MergeConfig, WhatsAppExport
from .output_format import OutputFormat, SiteConfiguration, output_registry
from .schema import MESSAGE_SCHEMA, WHATSAPP_SCHEMA
from .types import GroupSlug, PostSlug

# Import registry to auto-register implementations
from . import registry  # noqa: F401

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
    # Abstractions
    "InputSource",
    "InputMetadata",
    "OutputFormat",
    "SiteConfiguration",
    # Registries
    "input_registry",
    "output_registry",
]
