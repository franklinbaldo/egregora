from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar

from .expr.types import Table

__all__ = [
    "Table",
    "desc",
    "memtable",
    "row_number",
    "udf",
    "window",
]

_T = TypeVar("_T")


def memtable(
    data: Iterable[Mapping[str, Any]] | Iterable[Sequence[Any]] | Sequence[Any],
    schema: Any | None = ...,
) -> Table: ...


def desc(value: Any) -> Any: ...


def window(*, group_by: Any | None = ..., order_by: Any | None = ..., **_: Any) -> Any: ...


class _Overloadable:
    def over(self, window: Any) -> Any: ...


def row_number() -> _Overloadable: ...


class _ScalarNamespace:
    def python(self, func: Callable[..., _T]) -> Callable[..., _T]: ...

    def builtin(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., _T]], Callable[..., _T]]: ...


class _UDFNamespace:
    scalar: _ScalarNamespace


def schema(mapping: Mapping[str, Any]) -> Any: ...


def null() -> Any: ...


udf: _UDFNamespace
