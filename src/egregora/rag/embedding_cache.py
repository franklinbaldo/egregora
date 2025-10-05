"""Persistent caching utilities for Gemini embeddings using diskcache."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

import diskcache


@dataclass(slots=True)
class CachedEmbedding:
    """Container for cached embedding metadata."""

    dimension: int
    cached_at: datetime
    namespace: str | None = None

    def to_dict(self) -> dict[str, str | int]:
        payload: dict[str, str | int] = {
            "dimension": self.dimension,
            "cached_at": self.cached_at.isoformat(),
        }
        if self.namespace is not None:
            payload["namespace"] = self.namespace
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> CachedEmbedding:
        cached_at = payload.get("cached_at")
        timestamp = datetime.fromisoformat(str(cached_at)) if cached_at else datetime.utcnow()
        namespace = payload.get("namespace")
        return cls(
            dimension=int(payload.get("dimension", 0)),
            cached_at=timestamp,
            namespace=str(namespace) if namespace is not None else None,
        )


class EmbeddingCache:
    """Disk-based cache for embedding vectors using diskcache."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        model: str,
        dimension: int,
        extra: Mapping[str, str | int] | None = None,
    ) -> None:
        self.cache_dir = cache_dir / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._namespace = self._build_namespace(model=model, dimension=dimension, extra=extra)

        # Use diskcache for both embeddings and metadata
        self._cache = diskcache.Cache(str(self.cache_dir / "vectors"))
        self._metadata = diskcache.Cache(str(self.cache_dir / "metadata"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, text: str) -> list[float] | None:
        """Return a cached embedding for text if available."""
        text_hash = self._hash_text(text)

        # Check metadata first
        metadata = self._metadata.get(text_hash)
        if not metadata:
            return None

        # Verify namespace matches
        if isinstance(metadata, dict):
            entry = CachedEmbedding.from_dict(metadata)
            if entry.namespace and entry.namespace != self._namespace:
                return None

        # Get the actual embedding vector
        embedding = self._cache.get(text_hash)
        if not embedding or not isinstance(embedding, list):
            return None

        return [float(value) for value in embedding]

    def set(self, text: str, embedding: Iterable[float]) -> None:
        """Store embedding for text in the cache."""
        vector = [float(value) for value in embedding]
        text_hash = self._hash_text(text)

        # Store the embedding vector
        self._cache.set(text_hash, vector)

        # Store metadata
        entry = CachedEmbedding(
            dimension=len(vector),
            cached_at=datetime.utcnow(),
            namespace=self._namespace,
        )
        self._metadata.set(text_hash, entry.to_dict())

    def clear(self) -> None:
        """Remove all cached embeddings."""
        self._cache.clear()
        self._metadata.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _hash_text(self, text: str) -> str:
        """Generate a hash for the text with namespace."""
        payload = f"{self._namespace}::{text}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return digest

    def _build_namespace(
        self,
        *,
        model: str,
        dimension: int,
        extra: Mapping[str, str | int] | None = None,
    ) -> str:
        """Build a namespace string from model and parameters."""
        components = [f"model={model}", f"dimension={dimension}"]
        if extra:
            for key in sorted(extra):
                value = extra[key]
                components.append(f"{key}={value}")
        return "|".join(components)


__all__ = ["EmbeddingCache", "CachedEmbedding"]
