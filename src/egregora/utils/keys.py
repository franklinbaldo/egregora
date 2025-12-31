"""Key generation utilities."""

from __future__ import annotations

from hashlib import sha256
from typing import Annotated

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
