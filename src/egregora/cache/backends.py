"""Low-level cache backend protocols and implementations."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Protocol

import diskcache

from egregora.utils.exceptions import CacheKeyNotFoundError

if TYPE_CHECKING:
    from pathlib import Path


class CacheBackend(Protocol):
    """Abstract protocol for cache backends."""

    def get(self, key: str) -> Any: ...

    def set(self, key: str, value: Any, expire: float | None = None) -> None: ...

    def delete(self, key: str) -> None: ...

    def close(self) -> None: ...

    def __getitem__(self, key: str) -> Any: ...

    def __setitem__(self, key: str, value: Any) -> None: ...

    def __delitem__(self, key: str) -> None: ...


class DiskCacheBackend:
    """Adapter for diskcache.Cache to match CacheBackend protocol."""

    def __init__(self, directory: Path, **kwargs: Any) -> None:
        self._cache = diskcache.Cache(str(directory), **kwargs)

    def get(self, key: str) -> Any:
        try:
            return self._cache[key]
        except KeyError as e:
            raise CacheKeyNotFoundError(key) from e

    def set(self, key: str, value: Any, expire: float | None = None) -> None:
        self._cache.set(key, value, expire=expire)

    def delete(self, key: str) -> None:
        with contextlib.suppress(KeyError):
            del self._cache[key]

    def close(self) -> None:
        self._cache.close()

    def __getitem__(self, key: str) -> Any:
        return self._cache[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def __delitem__(self, key: str) -> None:
        del self._cache[key]
