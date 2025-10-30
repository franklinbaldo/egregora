"""Egregora v2: Ultra-simple WhatsApp to blog pipeline."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Protocol, cast

__version__ = "2.0.0"


class _ProcessExportCallable(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        ...


def process_whatsapp_export(*args: Any, **kwargs: Any) -> Any:
    """Proxy that loads the heavy pipeline module only when invoked."""

    module = import_module(".pipeline", package=__name__)
    implementation = cast(
        _ProcessExportCallable, getattr(module, "process_whatsapp_export")
    )
    return implementation(*args, **kwargs)


__all__ = ["process_whatsapp_export"]
