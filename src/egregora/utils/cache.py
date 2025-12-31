"""Unified tiered caching system for Egregora.

This module implements the Tiered Caching Architecture, providing distinct cache tiers
for different types of artifacts (assets, retrieval, synthesis) with granular
invalidation controls.
"""

from __future__ import annotations

import contextlib
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

import diskcache

from egregora.utils.exceptions import (
    CacheKeyNotFoundError,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


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


class CacheTier(str, Enum):
    """Enumeration of available cache tiers."""

    ENRICHMENT = "enrichment"  # L1: Assets (Invalidates on Format Change)
    RAG = "rag"  # L2: Retrieval (Invalidates on Model/Chunking Change)
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
        # L1: Assets - Uses JSONDisk for safety
        enrichment_dir = self.base_dir / "enrichment"
        self.enrichment = diskcache.Cache(str(enrichment_dir), disk=diskcache.JSONDisk)

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
