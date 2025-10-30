from __future__ import annotations

from typing import Any


class DataType: ...


def dtype(value: Any) -> DataType: ...


class Array(DataType): ...


class Map(DataType): ...


class Struct(DataType): ...


class String(DataType): ...


class Int64(DataType): ...

