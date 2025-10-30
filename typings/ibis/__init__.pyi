from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

from .expr.datatypes import DataType
from .expr.types import Column, Scalar, Table

Schema = Mapping[str, DataType]

class NullScalar:
    def cast(self, dtype: DataType) -> Column: ...

def schema(arg: Mapping[str, DataType]) -> Schema: ...

def memtable(
    data: Iterable[Mapping[str, Any]] | Iterable[Sequence[Any]] | Iterable[Any],
    *,
    schema: Schema | Mapping[str, DataType] | None = ...,
) -> Table: ...


def null() -> NullScalar: ...


class _ScalarNamespace:
    def builtin(
        self,
        *,
        name: str,
        signature: tuple[tuple[DataType | type, ...], DataType],
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


class _UDFNamespace:
    scalar: _ScalarNamespace


udf: _UDFNamespace
