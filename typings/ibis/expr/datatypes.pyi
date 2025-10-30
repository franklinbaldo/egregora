from __future__ import annotations

from typing import Any

class DataType: ...

class _CallableTypeFactory:
    def __call__(self, *args: Any, **kwargs: Any) -> DataType: ...


string: DataType

int64: DataType

float64: DataType

def date(nullable: bool = ...) -> DataType: ...

class _ArrayFactory:
    def __call__(self, value: DataType) -> DataType: ...

class _StringFactory(_CallableTypeFactory):
    ...

class _TimestampFactory:
    def __call__(self, *, timezone: str | None = ..., nullable: bool = ...) -> DataType: ...

Array: _ArrayFactory
String: _StringFactory
Timestamp: _TimestampFactory

__all__ = [
    "Array",
    "DataType",
    "String",
    "Timestamp",
    "date",
    "float64",
    "int64",
    "string",
]
