from __future__ import annotations

from typing import Any

class Console:
    is_terminal: bool
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def print(self, *args: Any, **kwargs: Any) -> None: ...
