from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .expr.types import Table

class Schema:
    def __getattr__(self, name: str) -> Any: ...
    def items(self) -> Iterable[tuple[str, Any]]: ...
    def names(self) -> Sequence[str]: ...
    def to_pyarrow(self) -> Any: ...

def schema(fields: Mapping[str, Any]) -> Schema: ...

def memtable(
    data: Mapping[str, Sequence[Any]]
    | Iterable[Mapping[str, Any]]
    | Sequence[Mapping[str, Any]]
    | Sequence[Sequence[Any]],
    schema: Schema | None = ...,
) -> Table: ...


def udf(*args: Any, **kwargs: Any) -> Any: ...


def literal(value: Any) -> Any: ...


def ifelse(condition: Any, true_value: Any, false_value: Any) -> Any: ...


def window(*args: Any, **kwargs: Any) -> Any: ...


def desc(value: Any) -> Any: ...


def row_number() -> Any: ...


def array(values: Sequence[Any]) -> Any: ...


def null() -> Any: ...


def read_csv(path: str | Path, **kwargs: Any) -> Table: ...


duckdb: Any

from . import expr as expr
