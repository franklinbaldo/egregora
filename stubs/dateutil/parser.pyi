from __future__ import annotations

from typing import Any

class ParserError(Exception):
    ...

def parse(timestr: str, *args: Any, **kwargs: Any) -> Any: ...

__all__ = ["ParserError", "parse"]
