"""Egregora v2: Multi-platform chat analysis and blog generation."""

# Import WhatsApp-specific functions for backward compatibility
from egregora.sources.whatsapp import discover_chat_file, process_whatsapp_export

__version__ = "2.0.0"

__all__ = [
    # WhatsApp pipeline (backward compatibility)
    "process_whatsapp_export",
    "discover_chat_file",
]
