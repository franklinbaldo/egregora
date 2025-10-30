from typing import Any, Iterable, Mapping

class Table:
    def to_pydict(self) -> dict[str, list[Any]]: ...
    @classmethod
    def from_pydict(cls, data: Mapping[str, list[Any]]) -> Table: ...

class RecordBatchReader:
    def read_all(self) -> Table: ...


def table(data: Mapping[str, list[Any]] | Iterable[Any]) -> Table: ...

from . import parquet as parquet


class ChunkedArray:
    def to_pylist(self) -> list[Any]: ...


class Error(Exception): ...


def array(data: Iterable[Any] | Mapping[str, Any], type: Any | None = ..., **kwargs: Any) -> Any: ...


def chunked_array(data: Iterable[Any], type: Any | None = ..., **kwargs: Any) -> ChunkedArray: ...


def read_metadata(source: Any, **kwargs: Any) -> Any: ...
