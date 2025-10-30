from __future__ import annotations

from typing import Any

class Console:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def print(self, *args: Any, **kwargs: Any) -> None: ...
    @property
    def is_terminal(self) -> bool: ...

__all__ = ["Console"]
