from __future__ import annotations

from typing import Any

class Environment:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def get_template(self, name: str) -> Template: ...

class Template:
    def render(self, *args: Any, **kwargs: Any) -> str: ...

class FileSystemLoader:
    def __init__(self, searchpath: Any, *args: Any, **kwargs: Any) -> None: ...

def select_autoescape(*args: Any, **kwargs: Any) -> Any: ...

__all__ = ["Environment", "Template", "FileSystemLoader", "select_autoescape"]
