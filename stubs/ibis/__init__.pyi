from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .expr.types import Table

class ScalarUDFDecorator:
    def __call__(self, func: Any) -> Any: ...

class ScalarNamespace:
    python: ScalarUDFDecorator

class UDFNamespace:
    scalar: ScalarNamespace

udf: UDFNamespace

def memtable(
    data: Iterable[Mapping[str, Any]] | Sequence[Mapping[str, Any]] | Any,
    *,
    schema: Any | None = ...,
) -> Table: ...

def schema(spec: Mapping[str, Any] | Sequence[tuple[str, Any]] | Any) -> Any: ...

def null() -> Any: ...
