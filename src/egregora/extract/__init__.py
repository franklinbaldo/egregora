"""Extract stage - Parse WhatsApp exports into structured data.

This package handles the extraction of data from WhatsApp ZIP exports.
"""

from .parser import parse_whatsapp_export

__all__ = ["parse_whatsapp_export"]
