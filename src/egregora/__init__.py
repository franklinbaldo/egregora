"""Egregora v2: Multi-platform chat analysis and blog generation."""

from egregora.sources.whatsapp import WhatsAppExport, discover_chat_file, process_whatsapp_export

__version__ = "2.0.0"
__all__ = ["WhatsAppExport", "discover_chat_file", "process_whatsapp_export"]
