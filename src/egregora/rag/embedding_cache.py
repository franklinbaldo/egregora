"""Disk-backed cache for embedding vectors using :mod:`diskcache`."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..cache import CacheMetadata, build_namespace, create_cache, load_vector, store_vector


class EmbeddingCache:
    """Simple cache that stores embedding vectors on disk."""

    def __init__(
        self,
        cache_dir: Path | None,
        *,
        model: str,
        dimension: int,
        extra: dict[str, str | int] | None = None,
        size_limit_mb: int | None = None,
    ) -> None:
        self._namespace = build_namespace(model=model, dimension=dimension, extra=extra)
        self._cache = create_cache(cache_dir, size_limit_mb=size_limit_mb)

    def get(self, text: str) -> list[float] | None:
        """Return the cached embedding for ``text`` when available."""

        return load_vector(self._cache, self._namespace, text)

    def set(self, text: str, embedding: Iterable[float]) -> None:
        """Store ``embedding`` for ``text``."""

        store_vector(self._cache, self._namespace, text, embedding)

    def clear(self) -> None:
        """Remove all cached vectors."""

        if not self._cache:
            return
        for key in list(self._cache.iterkeys()):  # type: ignore[attr-defined]
            self._cache.delete(key)


__all__ = ["EmbeddingCache", "CacheMetadata"]
