from __future__ import annotations

from typing import Any, Mapping, Sequence

from .datatypes import DataType

class Scalar:
    def execute(self) -> Any: ...


class Column:
    def cast(self, dtype: DataType) -> Column: ...
    def date(self) -> Column: ...


class Table:
    columns: Sequence[str]

    def schema(self) -> Mapping[str, DataType]: ...

    def mutate(self, **kwargs: Column | Scalar | Any) -> Table: ...

    def count(self) -> Scalar: ...

    def __getitem__(self, key: str) -> Column: ...
