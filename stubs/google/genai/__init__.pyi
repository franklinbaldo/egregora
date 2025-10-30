from __future__ import annotations

from typing import Any

from . import types

class Client:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    batches: Any
    files: Any
    models: Any

__all__ = ["Client", "types"]
