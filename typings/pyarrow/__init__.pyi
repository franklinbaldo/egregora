from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, TypeVar

_T = TypeVar("_T")

class Field:
    name: str
    type: Any

class Schema(Iterable[Field]):
    def __iter__(self) -> Iterator[Field]: ...

class RecordBatchReader:
    def read_all(self) -> Table: ...

class Array: ...

class Table:
    num_rows: int

    @classmethod
    def from_arrays(
        cls, arrays: Sequence[Any], schema: Schema | None = ..., **kwargs: Any
    ) -> Table: ...

    @classmethod
    def from_pandas(
        cls, df: Any, schema: Schema | None = ..., **kwargs: Any
    ) -> Table: ...

    @classmethod
    def from_pydict(cls, mapping: Mapping[str, Sequence[Any]]) -> Table: ...

    def to_pydict(self) -> dict[str, Sequence[Any]]: ...

    def column(self, index: int) -> Array: ...


def array(values: Sequence[Any], type: Any | None = ...) -> Array: ...

__all__ = [
    "Array",
    "Field",
    "RecordBatchReader",
    "Schema",
    "Table",
    "array",
]
