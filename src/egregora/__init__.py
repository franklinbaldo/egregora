"""Egregora v2: Multi-platform chat analysis and blog generation."""

from importlib import import_module
from typing import Any

__version__ = "2.0.0"
__all__ = [
    "process_whatsapp_export",
]

_LAZY_IMPORTS = {"process_whatsapp_export": "egregora.orchestration.write_pipeline"}


def __getattr__(name: str) -> Any:  # pragma: no cover - convenience import shim
    """Lazily import heavy modules to keep optional dependencies optional."""
    module_path = _LAZY_IMPORTS.get(name)
    if module_path:
        module = import_module(module_path)
        return getattr(module, name)
    msg = f"module 'egregora' has no attribute {name!r}"
    raise AttributeError(msg)
