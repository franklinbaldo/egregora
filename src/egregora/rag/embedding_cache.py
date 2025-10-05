"""Disk-backed cache for embedding vectors using :mod:`diskcache`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import hashlib

from diskcache import Cache


@dataclass(slots=True)
class CachedEmbedding:
    """Metadata associated with a cached embedding vector."""

    dimension: int
    namespace: str
    cached_at: str


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
        self._enabled = cache_dir is not None
        self._namespace = self._build_namespace(model=model, dimension=dimension, extra=extra)
        if not self._enabled:
            self._cache: Cache | None = None
            return

        directory = Path(cache_dir).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        size_limit = (
            None if size_limit_mb is None else max(0, int(size_limit_mb)) * 1024 * 1024
        )
        self._cache = Cache(directory=str(directory), size_limit=size_limit)

    def get(self, text: str) -> list[float] | None:
        """Return the cached embedding for ``text`` when available."""

        if not self._enabled or not self._cache:
            return None
        key = self._build_key(text)
        record = self._cache.get(key)
        if not record:
            return None
        if record.get("namespace") != self._namespace:
            return None
        vector = record.get("vector")
        if not isinstance(vector, list):
            return None
        return [float(value) for value in vector]

    def set(self, text: str, embedding: Iterable[float]) -> None:
        """Store ``embedding`` for ``text``."""

        if not self._enabled or not self._cache:
            return
        vector = [float(value) for value in embedding]
        record = {
            "vector": vector,
            "namespace": self._namespace,
            "metadata": CachedEmbedding(
                dimension=len(vector),
                namespace=self._namespace,
                cached_at=datetime.now(timezone.utc).isoformat(),
            ),
        }
        self._cache.set(self._build_key(text), record)

    def clear(self) -> None:
        """Remove all cached vectors."""

        if not self._enabled or not self._cache:
            return
        for key in list(self._cache.iterkeys()):
            self._cache.delete(key)

    def _build_key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self._namespace}::{text}".encode("utf-8")).hexdigest()
        return digest

    @staticmethod
    def _build_namespace(
        *,
        model: str,
        dimension: int,
        extra: dict[str, str | int] | None = None,
    ) -> str:
        parts = [f"model={model}", f"dimension={dimension}"]
        if extra:
            for key in sorted(extra):
                parts.append(f"{key}={extra[key]}")
        return "|".join(parts)


__all__ = ["EmbeddingCache", "CachedEmbedding"]
