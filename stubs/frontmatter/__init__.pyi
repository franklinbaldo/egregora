from __future__ import annotations

from typing import Any

def load(*args: Any, **kwargs: Any) -> Any: ...

def dumps(*args: Any, **kwargs: Any) -> str: ...

__all__ = ["load", "dumps"]
