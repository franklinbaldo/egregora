"""Egregora v2: Multi-platform chat analysis and blog generation."""

from egregora.input_adapters.whatsapp import WhatsAppAdapter, WhatsAppExport, discover_chat_file
from egregora.orchestration.write_pipeline import process_whatsapp_export

__version__ = "2.0.0"
__all__ = [
    "WhatsAppAdapter",
    "WhatsAppExport",
    "discover_chat_file",
    "process_whatsapp_export",
]
