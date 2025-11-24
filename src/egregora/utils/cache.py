"""Unified tiered caching system for Egregora.

This module implements the Tiered Caching Architecture, providing distinct cache tiers
for different types of artifacts (assets, retrieval, synthesis) with granular
invalidation controls.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Any, Protocol

import diskcache

logger = logging.getLogger(__name__)

ENRICHMENT_CACHE_VERSION = "v2"


def make_enrichment_cache_key(
    *,
    kind: Annotated[str, "The type of enrichment, e.g., 'url' or 'media'"],
    identifier: Annotated[str, "A unique identifier for the content being enriched"],
    version: Annotated[
        str, "A version string to invalidate caches when the format changes"
    ] = ENRICHMENT_CACHE_VERSION,
) -> Annotated[str, "A stable, unique cache key"]:
    """Create a stable cache key using the enrichment type and identifier.

    Args:
        kind: Entry type, e.g. "url" or "media".
        identifier: Unique identifier for the entry.
        version: Optional semantic version to bust caches when format changes.

    """
    raw = f"{version}:{kind}:{identifier}".encode()
    return sha256(raw).hexdigest()


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
        return self._cache.get(key)

    def set(self, key: str, value: Any, expire: float | None = None) -> None:
        self._cache.set(key, value, expire=expire)

    def delete(self, key: str) -> None:
        try:
            del self._cache[key]
        except KeyError:
            pass

    def close(self) -> None:
        self._cache.close()

    def __getitem__(self, key: str) -> Any:
        return self._cache[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def __delitem__(self, key: str) -> None:
        del self._cache[key]


@dataclass(slots=True)
class EnrichmentCache:
    """Disk-backed cache for enrichment markdown payloads."""

    backend: CacheBackend

    def load(
        self, key: Annotated[str, "The cache key to look up"]
    ) -> Annotated[dict[str, Any] | None, "The cached payload, or None if not found"]:
        """Return cached payload when present."""
        try:
            value = self.backend.get(key)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(
                "Failed to deserialize cache entry for key %s: %s. "
                "Clearing entry - will be regenerated.",
                key,
                e,
            )
            self.backend.delete(key)
            return None

        if value is None:
            return None
        if not isinstance(value, dict):
            logger.warning("Unexpected cache payload type for key %s; clearing entry", key)
            self.backend.delete(key)
            return None
        return value

    def store(
        self,
        key: Annotated[str, "The cache key to store the payload under"],
        payload: Annotated[dict[str, Any], "The payload to store"],
    ) -> None:
        """Persist enrichment payload."""
        self.backend.set(key, payload, expire=None)
        logger.debug("Cached enrichment entry for key %s", key)

    def delete(self, key: Annotated[str, "The cache key to delete"]) -> None:
        """Remove an entry from the cache if present."""
        self.backend.delete(key)

    def close(self) -> None:
        """Release underlying cache resources."""
        self.backend.close()


class CacheTier(str, Enum):
    """Enumeration of available cache tiers."""

    ENRICHMENT = "enrichment"  # L1: Assets (Immutable)
    RAG = "rag"  # L2: Retrieval (Invalidates on Index Change)
    WRITER = "writer"  # L3: Synthesis (Invalidates on Prompt/Data Change)


class PipelineCache:
    """Unified tiered caching system.

    Manages separate DiskCache instances for each tier to allow granular invalidation
    and distinct eviction policies.
    """

    def __init__(
        self,
        base_dir: Path,
        refresh_tiers: set[str] | None = None,
    ) -> None:
        """Initialize the pipeline cache.

        Args:
            base_dir: Base directory for cache storage.
            refresh_tiers: Set of tier names to force-refresh.
                           'all' refreshes everything.

        """
        self.base_dir = base_dir.expanduser().resolve()
        self.refresh_tiers = refresh_tiers or set()

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Initialize tiers
        # L1: Assets - Uses JSONDisk for safety, mirroring old EnrichmentCache behavior
        enrichment_dir = self.base_dir / "enrichment"
        # Inject backend into EnrichmentCache
        enrichment_backend = DiskCacheBackend(enrichment_dir, disk=diskcache.JSONDisk)
        self.enrichment = EnrichmentCache(backend=enrichment_backend)

        # L2: Retrieval - Standard pickle disk is fine for internal artifacts
        rag_dir = self.base_dir / "rag"
        self.rag = diskcache.Cache(str(rag_dir))

        # L3: Synthesis - Stores Pydantic model dictionaries
        writer_dir = self.base_dir / "writer"
        self.writer = diskcache.Cache(str(writer_dir))

        logger.debug("Initialized PipelineCache at %s", self.base_dir)
        if self.refresh_tiers:
            logger.info("Refresh requested for tiers: %s", self.refresh_tiers)

    def should_refresh(self, tier: CacheTier) -> bool:
        """Check if a specific tier was requested for refresh via CLI."""
        return "all" in self.refresh_tiers or tier.value in self.refresh_tiers

    def close(self) -> None:
        """Close all underlying cache connections."""
        self.enrichment.close()
        self.rag.close()
        self.writer.close()
