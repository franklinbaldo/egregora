"""Caches for agent-related artifacts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, Any

from egregora.utils.cache_backend import CacheBackend
from egregora.utils.exceptions import CacheDeserializationError, CachePayloadTypeError

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


@dataclass(slots=True)
class EnrichmentCache:
    """Disk-backed cache for enrichment markdown payloads."""

    backend: CacheBackend

    def load(
        self, key: Annotated[str, "The cache key to look up"]
    ) -> Annotated[dict[str, Any], "The cached payload, or None if not found"]:
        """Return cached payload when present."""
        try:
            value = self.backend.get(key)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(
                "Failed to deserialize cache entry for key %s: %s. Clearing entry - will be regenerated.",
                key,
                e,
            )
            self.backend.delete(key)
            raise CacheDeserializationError(key, e) from e

        if not isinstance(value, dict):
            logger.warning("Unexpected cache payload type for key %s; clearing entry", key)
            self.backend.delete(key)
            raise CachePayloadTypeError(key, type(value))
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
