"""Registry initialization for input sources and output formats.

This module automatically registers all available input sources and output formats
when imported. Add new implementations to this module to make them available.
"""

from ..ingestion.whatsapp_input import WhatsAppInputSource
from ..init.mkdocs_output import MkDocsOutputFormat
from .input_source import input_registry
from .output_format import output_registry


def register_all() -> None:
    """Register all available input sources and output formats."""
    # Register input sources
    input_registry.register(WhatsAppInputSource)

    # Register output formats
    output_registry.register(MkDocsOutputFormat)


# Auto-register on import
register_all()


__all__ = [
    "input_registry",
    "output_registry",
    "register_all",
]
