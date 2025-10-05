"""Shared cache utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping
import hashlib

from diskcache import Cache


@dataclass(slots=True)
class CachedEmbedding:
    """Metadata associated with a cached embedding vector."""

    dimension: int
    namespace: str
    cached_at: str


def _normalise_extra(extra: Mapping[str, str | int] | None) -> tuple[tuple[str, str], ...]:
    if not extra:
        return tuple()
    items: list[tuple[str, str]] = []
    for key in sorted(extra):
        value = extra[key]
        items.append((key, str(value)))
    return tuple(items)


def build_embedding_namespace(
    *,
    model: str,
    dimension: int,
    extra: Mapping[str, str | int] | None = None,
) -> str:
    """Create a stable namespace for embedding caches."""

    parts = [("model", model), ("dimension", str(dimension))]
    parts.extend(_normalise_extra(extra))
    return "|".join(f"{key}={value}" for key, value in parts)


def _hash_namespace_text(namespace: str, text: str, *, kind: str | None = None) -> str:
    segments = [namespace]
    if kind:
        segments.append(kind)
    segments.append(text)
    digest = hashlib.sha256("::".join(segments).encode("utf-8")).hexdigest()
    return digest


def create_embedding_cache(
    namespace: str,
    cache_dir: Path | str | None,
    *,
    size_limit_mb: int | None = None,
) -> Cache | None:
    """Create a :class:`diskcache.Cache` for embedding storage."""

    if cache_dir is None:
        return None
    directory = Path(cache_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, int] = {}
    if size_limit_mb is not None:
        kwargs["size_limit"] = max(0, int(size_limit_mb)) * 1024 * 1024
    return Cache(directory=str(directory), **kwargs)


def load_cached_embedding(
    cache: Cache,
    namespace: str,
    text: str,
    *,
    kind: str | None = None,
) -> list[float] | None:
    """Load an embedding vector from ``cache`` if present for ``text``."""

    record = cache.get(_hash_namespace_text(namespace, text, kind=kind))
    if not isinstance(record, dict):
        return None
    if record.get("namespace") != namespace:
        return None
    vector = record.get("vector")
    if not isinstance(vector, list):
        return None
    return [float(value) for value in vector]


def store_cached_embedding(
    cache: Cache,
    namespace: str,
    text: str,
    values: Iterable[float],
    *,
    kind: str | None = None,
) -> None:
    """Persist ``values`` for ``text`` in ``cache``."""

    vector = [float(value) for value in values]
    record = {
        "vector": vector,
        "namespace": namespace,
        "metadata": CachedEmbedding(
            dimension=len(vector),
            namespace=namespace,
            cached_at=datetime.now(timezone.utc).isoformat(),
        ),
    }
    cache.set(_hash_namespace_text(namespace, text, kind=kind), record)


__all__ = [
    "CachedEmbedding",
    "build_embedding_namespace",
    "create_embedding_cache",
    "load_cached_embedding",
    "store_cached_embedding",
]
