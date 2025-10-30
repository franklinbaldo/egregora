from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any

class DataType: ...

class Field:
    name: str
    type: DataType

class Schema:
    names: Sequence[str]
    def __iter__(self) -> Iterator[Field]: ...

class Array:
    ...

class ChunkedArray:
    def to_pylist(self) -> list[Any]: ...

class Table:
    column_names: Sequence[str]
    num_rows: int
    num_columns: int
    schema: Schema

    def column(self, index: int) -> ChunkedArray: ...
    def to_pydict(self) -> dict[str, Any]: ...

    @classmethod
    def from_arrays(cls, arrays: Sequence[Any], schema: Schema) -> Table: ...
    @classmethod
    def from_pydict(cls, mapping: Mapping[str, Iterable[Any]]) -> Table: ...
    @classmethod
    def from_pandas(
        cls,
        obj: Any,
        schema: Schema | None = ...,
        preserve_index: bool = ...,
        safe: bool = ...,
    ) -> Table: ...


class RecordBatchReader:
    def read_all(self) -> Table: ...


def array(data: Iterable[Any], type: DataType | None = ...) -> Array: ...

__all__ = [
    "Array",
    "ChunkedArray",
    "DataType",
    "Field",
    "RecordBatchReader",
    "Schema",
    "Table",
    "array",
]
