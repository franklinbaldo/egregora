from __future__ import annotations

import json

import pytest

from egregora.utils.cache import (
    CacheKeyNotFoundError,
    DiskCacheBackend,
    EnrichmentCache,
)
from egregora.utils.cache_backend import CacheBackend
from egregora.utils.exceptions import CacheDeserializationError, CachePayloadTypeError


def test_disk_cache_backend_get_raises_key_not_found_error(tmp_path):
    """Verify `get` raises CacheKeyNotFoundError for a missing key."""
    backend = DiskCacheBackend(tmp_path)
    with pytest.raises(CacheKeyNotFoundError, match="Key not found in cache: 'missing-key'"):
        backend.get("missing-key")


def test_enrichment_cache_deserialization_error(mocker):
    """Test that EnrichmentCache handles deserialization errors."""
    backend = mocker.MagicMock(spec=CacheBackend)
    backend.get.side_effect = json.JSONDecodeError("mock error", "", 0)
    cache = EnrichmentCache(backend)
    with pytest.raises(CacheDeserializationError):
        cache.load("test-key")


def test_enrichment_cache_payload_type_error(mocker):
    """Test that EnrichmentCache handles payload type errors."""
    backend = mocker.MagicMock(spec=CacheBackend)
    backend.get.return_value = "not a dict"
    cache = EnrichmentCache(backend)
    with pytest.raises(CachePayloadTypeError):
        cache.load("test-key")
