"""Persistent caches for enrichment and other pipeline artifacts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import diskcache

logger = logging.getLogger(__name__)

ENRICHMENT_CACHE_VERSION = "v1"


def make_enrichment_cache_key(
    *,
    kind: str,
    identifier: str,
    version: str = ENRICHMENT_CACHE_VERSION,
) -> str:
    """
    Create a stable cache key using the enrichment type and identifier.

    Args:
        kind: Entry type, e.g. "url" or "media".
        identifier: Unique identifier for the entry.
        version: Optional semantic version to bust caches when format changes.
    """
    raw = f"{version}:{kind}:{identifier}".encode()
    return sha256(raw).hexdigest()


@dataclass(slots=True)
class EnrichmentCache:
    """Disk-backed cache for enrichment markdown payloads."""

    directory: Path | None = None
    _cache: diskcache.Cache | None = None

    def __post_init__(self) -> None:
        base_dir = self.directory or Path(".egregora-cache") / "enrichments"
        base_dir = base_dir.expanduser().resolve()
        base_dir.mkdir(parents=True, exist_ok=True)

        logger.debug("Initializing enrichment cache at %s", base_dir)
        self._cache = diskcache.Cache(str(base_dir))
        self.directory = base_dir

    def load(self, key: str) -> dict[str, Any] | None:
        """Return cached payload when present."""
        if self._cache is None:
            return None
        value = self._cache.get(key)
        if value is None:
            return None
        if not isinstance(value, dict):
            logger.warning("Unexpected cache payload type for key %s; clearing entry", key)
            self.delete(key)
            return None
        return value

    def store(self, key: str, payload: dict[str, Any]) -> None:
        """Persist enrichment payload."""
        if self._cache is None:
            raise RuntimeError("Cache not initialised")
        self._cache.set(key, payload, expire=None)
        logger.debug("Cached enrichment entry for key %s", key)

    def delete(self, key: str) -> None:
        """Remove an entry from the cache if present."""
        try:
            if self._cache is not None:
                del self._cache[key]
        except KeyError:
            return

    def close(self) -> None:
        """Release underlying cache resources."""
        if self._cache is not None:
            self._cache.close()
            self._cache = None
