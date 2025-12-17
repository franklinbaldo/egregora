"""Unified tiered caching system for Egregora.

This module implements simple disk-based caching using diskcache.
"""

from __future__ import annotations

import logging
from hashlib import sha256
from pathlib import Path
from typing import Annotated

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


class PipelineCache:
    """Unified caching system.

    Manages separate DiskCache instances for each tier.
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
        # L1: Assets - Uses JSONDisk for dict compatibility
        enrichment_dir = self.base_dir / "enrichment"
        self.enrichment = diskcache.Cache(str(enrichment_dir), disk=diskcache.JSONDisk)

        # L2: Retrieval
        rag_dir = self.base_dir / "rag"
        self.rag = diskcache.Cache(str(rag_dir))

        # L3: Synthesis
        writer_dir = self.base_dir / "writer"
        self.writer = diskcache.Cache(str(writer_dir))

        logger.debug("Initialized PipelineCache at %s", self.base_dir)
        if self.refresh_tiers:
            logger.info("Refresh requested for tiers: %s", self.refresh_tiers)

    def should_refresh(self, tier: str) -> bool:
        """Check if a specific tier was requested for refresh via CLI."""
        return "all" in self.refresh_tiers or tier in self.refresh_tiers

    def close(self) -> None:
        """Close all underlying cache connections."""
        self.enrichment.close()
        self.rag.close()
        self.writer.close()
