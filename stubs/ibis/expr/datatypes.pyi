from typing import Any

class DataType:
    def __getattr__(self, name: str) -> Any: ...


def Timestamp(
    *,
    timezone: str | None = ...,
    scale: int | None = ...,
    nullable: bool | None = ...,
) -> DataType: ...


def Date(*, nullable: bool | None = ...) -> DataType: ...


def Array(item_type: DataType, *, nullable: bool | None = ...) -> DataType: ...


def literal(value: Any) -> Any: ...


string: DataType
int64: DataType
float64: DataType
