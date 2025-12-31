from __future__ import annotations

import pytest

from egregora.utils.cache import (
    CacheDeserializationError,
    CachePayloadTypeError,
)
from egregora.utils.exceptions import CacheKeyNotFoundError
from egregora.utils.cache_backend import DiskCacheBackend
from egregora.agents.cache import EnrichmentCache


def test_disk_cache_backend_get_raises_key_not_found_error(tmp_path):
    """Verify `get` raises CacheKeyNotFoundError for a missing key."""
    backend = DiskCacheBackend(tmp_path)
    with pytest.raises(CacheKeyNotFoundError, match="Key not found in cache: 'missing-key'"):
        backend.get("missing-key")
