"""Shared cache helpers built on top of :mod:`diskcache`."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from diskcache import Cache

__all__ = [
    "CacheMetadata",
    "build_namespace",
    "create_cache",
    "hash_key",
    "load_vector",
    "store_vector",
]


@dataclass(slots=True)
class CacheMetadata:
    """Minimal metadata stored alongside cached vectors."""

    dimension: int
    namespace: str
    cached_at: str


def _normalise_extra(extra: Mapping[str, str | int] | None) -> tuple[tuple[str, str], ...]:
    if not extra:
        return tuple()
    items: list[tuple[str, str]] = []
    for key in sorted(extra):
        items.append((key, str(extra[key])))
    return tuple(items)


def build_namespace(
    *,
    model: str,
    dimension: int,
    extra: Mapping[str, str | int] | None = None,
) -> str:
    """Return a stable namespace that identifies cached vectors."""

    parts = [("model", model), ("dimension", str(dimension))]
    parts.extend(_normalise_extra(extra))
    return "|".join(f"{key}={value}" for key, value in parts)


def create_cache(
    cache_dir: Path | str | None,
    *,
    size_limit_mb: int | None = None,
) -> Cache | None:
    """Instantiate a :class:`diskcache.Cache` rooted at ``cache_dir``."""

    if cache_dir is None:
        return None
    directory = Path(cache_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, int] = {}
    if size_limit_mb is not None:
        kwargs["size_limit"] = max(0, int(size_limit_mb)) * 1024 * 1024
    return Cache(directory=str(directory), **kwargs)


def hash_key(namespace: str, text: str, *, kind: str | None = None) -> str:
    """Return a SHA256 key for ``text`` scoped to ``namespace``."""

    segments = [namespace]
    if kind:
        segments.append(kind)
    segments.append(text)
    return hashlib.sha256("::".join(segments).encode("utf-8")).hexdigest()


def load_vector(
    cache: Cache | None,
    namespace: str,
    text: str,
    *,
    kind: str | None = None,
) -> list[float] | None:
    """Load a cached vector if present."""

    if cache is None:
        return None
    record = cache.get(hash_key(namespace, text, kind=kind))
    if not isinstance(record, dict):
        return None
    if record.get("namespace") != namespace:
        return None
    vector = record.get("vector")
    if not isinstance(vector, list):
        return None
    return [float(value) for value in vector]


def store_vector(
    cache: Cache | None,
    namespace: str,
    text: str,
    values: Iterable[float],
    *,
    kind: str | None = None,
) -> CacheMetadata | None:
    """Persist ``values`` in ``cache`` when caching is enabled."""

    if cache is None:
        return None
    vector = [float(value) for value in values]
    metadata = CacheMetadata(
        dimension=len(vector),
        namespace=namespace,
        cached_at=datetime.now(UTC).isoformat(),
    )
    cache.set(
        hash_key(namespace, text, kind=kind),
        {
            "vector": vector,
            "namespace": namespace,
            "metadata": metadata,
        },
    )
    return metadata
