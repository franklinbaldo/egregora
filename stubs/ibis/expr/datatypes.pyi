from __future__ import annotations

from typing import Any

class DataType:
    ...

class Timestamp(DataType):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Date(DataType):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class String(DataType):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Array(DataType):
    def __init__(self, value_type: DataType, *args: Any, **kwargs: Any) -> None: ...

class Struct(DataType):
    def __init__(self, fields: Any, *args: Any, **kwargs: Any) -> None: ...

int64: DataType
float64: DataType
string: DataType

__all__ = [
    "DataType",
    "Timestamp",
    "Date",
    "String",
    "Array",
    "Struct",
    "int64",
    "float64",
    "string",
]
