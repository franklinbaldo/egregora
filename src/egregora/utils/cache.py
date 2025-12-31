"""Unified tiered caching system for Egregora.

This module implements the Tiered Caching Architecture, providing distinct cache tiers
for different types of artifacts (assets, retrieval, synthesis) with granular
invalidation controls.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

import diskcache
from pydantic import BaseModel, ValidationError

from egregora.utils.cache_backend import CacheBackend, DiskCacheBackend
from egregora.utils.exceptions import (
    CacheDeserializationError,
    CacheKeyNotFoundError,
    CachePayloadTypeError,
)

from egregora.agents.cache import EnrichmentCache
from egregora.utils.cache_backend import DiskCacheBackend

if TYPE_CHECKING:
    from pathlib import Path


class EnrichmentCache:
    """Cache for storing and retrieving enrichment data using a pluggable backend."""

    def __init__(self, backend: CacheBackend) -> None:
        """Initialize the cache with a storage backend."""
        self.backend = backend

    def get(self, key: str, model: type[BaseModel]) -> BaseModel | None:
        """Retrieve and validate an item from the cache.

        Args:
            key: The cache key.
            model: The Pydantic model to validate the data against.

        Returns:
            The validated Pydantic model instance, or None if the key is not found.

        Raises:
            CacheDeserializationError: If the data is corrupted or fails validation.
            CachePayloadTypeError: If the retrieved payload is not a dictionary.

        """
        try:
            data = self.backend.get(key)
            if data is None:
                return None

            if not isinstance(data, dict):
                raise CachePayloadTypeError(key=key, payload_type=type(data))

            return model.model_validate(data)

        except (ValidationError, TypeError) as e:
            raise CacheDeserializationError(key=key, original_exception=e) from e
        except CacheKeyNotFoundError:
            return None

    def set(self, key: str, value: BaseModel) -> None:
        """Set an item in the cache.

        Args:
            key: The cache key.
            value: The Pydantic model instance to store.

        """
        self.backend.set(key, value.model_dump(mode="json"))

    def close(self) -> None:
        """Close the cache and its backend."""
        self.backend.close()


def make_enrichment_cache_key(content: str, salt: str, model_name: str | None = None) -> str:
    """Create a consistent cache key for enrichment data."""
    import hashlib

    hasher = hashlib.sha256()
    hasher.update(content.encode("utf-8"))
    hasher.update(salt.encode("utf-8"))
    if model_name:
        hasher.update(model_name.encode("utf-8"))
    return hasher.hexdigest()


logger = logging.getLogger(__name__)


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
