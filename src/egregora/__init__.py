"""Egregora v2: Ultra-simple WhatsApp to blog pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__version__ = "2.0.0"

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from collections.abc import Callable

    process_whatsapp_export: Callable[..., Any]
else:
    def process_whatsapp_export(*args: Any, **kwargs: Any) -> Any:
        from .pipeline import process_whatsapp_export as _process_whatsapp_export

        return _process_whatsapp_export(*args, **kwargs)

__all__ = [
    "process_whatsapp_export",
]
