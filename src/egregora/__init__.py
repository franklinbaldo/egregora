"""Egregora v2: Multi-platform chat analysis and blog generation."""

from importlib import import_module
from typing import Any

__version__ = "2.0.0"
__all__ = [
    "WhatsAppAdapter",
    "WhatsAppExport",
    "discover_chat_file",
    "process_whatsapp_export",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - convenience import shim
    """Lazily import heavy modules to keep optional dependencies optional."""
    if name in {"WhatsAppAdapter", "WhatsAppExport", "discover_chat_file"}:
        module = import_module("egregora.input_adapters.whatsapp")
        return getattr(module, name)
    if name == "process_whatsapp_export":
        module = import_module("egregora.orchestration.write_pipeline")
        return getattr(module, name)
    raise AttributeError(f"module 'egregora' has no attribute {name!r}")
