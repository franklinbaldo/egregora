"""Egregora v2: Multi-platform chat analysis and blog generation."""

# Import WhatsApp-specific functions for backward compatibility
from egregora.sources.whatsapp import WhatsAppExport, discover_chat_file, process_whatsapp_export

__version__ = "2.0.0"

__all__ = [
    "WhatsAppExport",
    "discover_chat_file",
    # WhatsApp pipeline (backward compatibility)
    "process_whatsapp_export",
]
