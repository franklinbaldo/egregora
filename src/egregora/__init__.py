"""Egregora v2: Ultra-simple WhatsApp to blog pipeline."""

from __future__ import annotations

from typing import Any

__version__ = "2.0.0"


def process_whatsapp_export(*args: Any, **kwargs: Any) -> Any:
    """Proxy ``process_whatsapp_export`` to avoid importing heavy modules at import time."""

    from .pipeline import process_whatsapp_export as _process_whatsapp_export

    return _process_whatsapp_export(*args, **kwargs)


__all__ = [
    "process_whatsapp_export",
]
