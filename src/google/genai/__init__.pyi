from __future__ import annotations

from typing import Any, Protocol

from . import types

__all__ = ["Client", "types"]

class _ModelsAPI(Protocol):
    def generate_content(self, *args: Any, **kwargs: Any) -> types.GenerateContentResponse: ...

class Client:
    models: _ModelsAPI
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
