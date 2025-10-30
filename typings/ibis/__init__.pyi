from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .expr.datatypes import DataType
from .expr.types import Table

class Schema:
    names: Sequence[str]

    def __init__(self, fields: Mapping[str, DataType]): ...

    def items(self) -> Iterable[tuple[str, DataType]]: ...

    def to_pyarrow(self) -> Any: ...


def schema(fields: Mapping[str, DataType]) -> Schema: ...

def array(values: Sequence[Any], type: Any | None = ...) -> Any: ...

class _DuckDBNamespace:
    def from_connection(self, connection: Any) -> DuckDBBackend: ...
    def connect(self, database: str | None = ..., **kwargs: Any) -> DuckDBBackend: ...

class DuckDBBackend:
    def read_parquet(self, source: str | Any) -> Table: ...
    def table(self, name: str) -> Table: ...

class _Options:
    default_backend: Any

duckdb: _DuckDBNamespace
options: _Options | None


def memtable(data: Any, *args: Any, **kwargs: Any) -> Table: ...


def desc(value: Any) -> Any: ...


def row_number() -> Any: ...


def window(*args: Any, **kwargs: Any) -> Any: ...

__all__ = [
    "Schema",
    "Table",
    "array",
    "duckdb",
    "desc",
    "memtable",
    "options",
    "row_number",
    "schema",
    "window",
]
