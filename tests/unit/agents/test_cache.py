from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from egregora.agents.cache import EnrichmentCache, make_enrichment_cache_key
from egregora.utils.exceptions import (
    CacheDeserializationError,
    CacheKeyNotFoundError,
    CachePayloadTypeError,
)


def test_make_enrichment_cache_key():
    """Verify that the cache key is stable and unique."""
    key1 = make_enrichment_cache_key(kind="url", identifier="https://example.com")
    key2 = make_enrichment_cache_key(kind="url", identifier="https://example.com")
    key3 = make_enrichment_cache_key(kind="url", identifier="https://example.com/other")
    assert key1 == key2
    assert key1 != key3


def test_make_enrichment_cache_key_with_version():
    """Verify that the cache key changes with the version."""
    key1 = make_enrichment_cache_key(kind="url", identifier="https://example.com", version="v1")
    key2 = make_enrichment_cache_key(kind="url", identifier="https://example.com", version="v2")
    assert key1 != key2


def test_enrichment_cache_load_propagates_key_not_found_error():
    """Verify `EnrichmentCache.load` propagates CacheKeyNotFoundError from the backend."""
    mock_backend = MagicMock()
    mock_backend.get.side_effect = CacheKeyNotFoundError("test-key")

    cache = EnrichmentCache(backend=mock_backend)

    with pytest.raises(CacheKeyNotFoundError):
        cache.load("test-key")

    mock_backend.get.assert_called_once_with("test-key")


def test_enrichment_cache_load_raises_deserialization_error():
    """Verify `EnrichmentCache.load` raises CacheDeserializationError on backend error."""
    mock_backend = MagicMock()
    mock_backend.get.side_effect = TypeError("corrupted data")

    cache = EnrichmentCache(backend=mock_backend)

    with pytest.raises(CacheDeserializationError):
        cache.load("test-key")

    mock_backend.delete.assert_called_once_with("test-key")


def test_enrichment_cache_load_raises_payload_type_error():
    """Verify `EnrichmentCache.load` raises CachePayloadTypeError for invalid data types."""
    mock_backend = MagicMock()
    mock_backend.get.return_value = "not a dict"

    cache = EnrichmentCache(backend=mock_backend)

    with pytest.raises(CachePayloadTypeError):
        cache.load("test-key")

    mock_backend.delete.assert_called_once_with("test-key")


def test_enrichment_cache_store():
    """Verify `EnrichmentCache.store` calls the backend's set method."""
    mock_backend = MagicMock()
    cache = EnrichmentCache(backend=mock_backend)
    payload = {"data": "test"}

    cache.store("test-key", payload)

    mock_backend.set.assert_called_once_with("test-key", payload, expire=None)


def test_enrichment_cache_delete():
    """Verify `EnrichmentCache.delete` calls the backend's delete method."""
    mock_backend = MagicMock()
    cache = EnrichmentCache(backend=mock_backend)

    cache.delete("test-key")

    mock_backend.delete.assert_called_once_with("test-key")


def test_enrichment_cache_close():
    """Verify `EnrichmentCache.close` calls the backend's close method."""
    mock_backend = MagicMock()
    cache = EnrichmentCache(backend=mock_backend)

    cache.close()

    mock_backend.close.assert_called_once()
