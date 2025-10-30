from __future__ import annotations

from typing import Any

__all__ = [
    "DataType",
    "Date",
    "Schema",
    "String",
    "Timestamp",
    "dtype",
]


class DataType:
    ...


class Timestamp(DataType):
    timezone: str | None
    scale: int | None

    def __init__(self, timezone: str | None = ..., scale: int | None = ...) -> None: ...


class Date(DataType):
    def __init__(self) -> None: ...


class String(DataType):
    def __init__(self) -> None: ...


def dtype(value: Any) -> DataType: ...


def Schema(mapping: Any) -> Any: ...
