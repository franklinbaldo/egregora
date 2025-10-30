"""Egregora v2: Ultra-simple WhatsApp to blog pipeline."""

from .orchestration import process_whatsapp_export

__version__ = "2.0.0"

__all__ = [
    "process_whatsapp_export",
]
