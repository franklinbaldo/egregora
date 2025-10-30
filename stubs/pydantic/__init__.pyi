from __future__ import annotations

from typing import Any, Callable, TypeVar

T = TypeVar("T")

class BaseModel:
    model_config: dict[str, Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...

class FieldInfo:
    ...

def Field(*args: Any, **kwargs: Any) -> Any: ...

def field_validator(*args: Any, **kwargs: Any) -> Callable[[Callable[..., T]], Callable[..., T]]: ...

def AliasChoices(*args: Any, **kwargs: Any) -> Any: ...

def ConfigDict(*args: Any, **kwargs: Any) -> dict[str, Any]: ...

__all__ = [
    "BaseModel",
    "Field",
    "field_validator",
    "AliasChoices",
    "ConfigDict",
]
