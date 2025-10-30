from __future__ import annotations

from typing import Generic, TypeVar

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class Cache(Generic[_KT, _VT]):
    def __init__(self, directory: str, *, size_limit: int | None = ..., **kwargs: object) -> None: ...

    def get(self, key: _KT, default: _VT | None = ..., read: bool = ...) -> _VT | None: ...

    def set(
        self,
        key: _KT,
        value: _VT,
        expire: float | int | None = ...,
        tag: str | None = ...,
        retry: bool = ...,
    ) -> bool: ...

    def close(self) -> None: ...

    def __delitem__(self, key: _KT) -> None: ...
