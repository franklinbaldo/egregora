from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Callable, Protocol, TypeVar

T_co = TypeVar("T_co", covariant=True)


class Scalar(Protocol[T_co]):
    def execute(self) -> T_co: ...


class Schema(Protocol):
    names: Sequence[str]


class Table(Protocol):
    def count(self) -> Scalar[int]: ...
    def execute(self) -> Any: ...
    def mutate(self, *args: Any, **kwargs: Any) -> Table: ...
    def schema(self) -> Schema: ...
    def union(self, other: Table, *, distinct: bool = ...) -> Table: ...
    def order_by(self, *columns: Any) -> Table: ...
    def __getattr__(self, name: str) -> Any: ...


def memtable(
    data: Iterable[Mapping[str, Any]] | Sequence[Mapping[str, Any]] | Any,
    *,
    schema: Any | None = ...,
) -> Table: ...


class _PythonScalarNamespace(Protocol):
    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]: ...


class _ScalarNamespace(Protocol):
    python: _PythonScalarNamespace


class _UDFNamespace(Protocol):
    scalar: _ScalarNamespace


udf: _UDFNamespace

