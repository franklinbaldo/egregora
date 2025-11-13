"""Compatibility shims for WhatsApp orchestration helpers.

The WhatsApp-specific helpers moved to :mod:`egregora.sources.whatsapp` during
the input adapter consolidation. This module keeps the historic
``egregora.orchestration.whatsapp`` import path working while delegating to the
new implementation.
"""

from egregora.sources.whatsapp import discover_chat_file, process_whatsapp_export

__all__ = ["discover_chat_file", "process_whatsapp_export"]
