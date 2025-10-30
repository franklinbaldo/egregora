from __future__ import annotations

from typing import Optional

class DataType:
    ...


class Timestamp(DataType):
    timezone: Optional[str]
    scale: Optional[int]

    def __init__(self, *, timezone: Optional[str] = ..., scale: Optional[int] = ...) -> None: ...


class Date(DataType):
    def __init__(self) -> None: ...


class String(DataType):
    def __init__(self) -> None: ...


string: DataType
