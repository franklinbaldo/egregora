from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

class Array:
    def to_pylist(self) -> list[Any]: ...

class ChunkedArray:
    def __iter__(self) -> Iterable[Any]: ...
    def to_pylist(self) -> list[Any]: ...

class Schema:
    names: Sequence[str]

class RecordBatchReader:
    def read_all(self) -> Table: ...

class Table:
    column_names: Sequence[str]
    num_rows: int

    def column(self, index: int) -> Array: ...
    def to_pydict(self) -> dict[str, list[Any]]: ...
    def to_pylist(self) -> list[Mapping[str, Any]]: ...
    def select(self, *args: Any, **kwargs: Any) -> Table: ...

    @classmethod
    def from_arrays(cls, arrays: Sequence[Array], schema: Schema) -> Table: ...

    @classmethod
    def from_pandas(cls, *args: Any, **kwargs: Any) -> Table: ...

    @classmethod
    def from_pydict(cls, data: Mapping[str, Sequence[Any]], schema: Schema | None = ...) -> Table: ...

class Field:
    type: Any

class DataType:
    ...

def array(values: Sequence[Any], type: Any | None = ...) -> Array: ...

def schema(fields: Mapping[str, Any]) -> Schema: ...

def __getattr__(name: str) -> Any: ...

__all__ = [
    "Array",
    "ChunkedArray",
    "Schema",
    "RecordBatchReader",
    "Table",
    "Field",
    "DataType",
    "array",
    "schema",
]
