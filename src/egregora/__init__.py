"""Egregora v2: Multi-platform chat analysis and blog generation."""

from egregora.input_adapters.whatsapp.models import WhatsAppExport
from egregora.orchestration.whatsapp import discover_chat_file, process_whatsapp_export

__version__ = "2.0.0"
__all__ = ["WhatsAppExport", "discover_chat_file", "process_whatsapp_export"]
