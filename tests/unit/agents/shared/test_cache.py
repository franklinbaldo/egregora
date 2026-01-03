"""Tests for shared agent cache utilities."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from egregora.agents.shared.cache import (
    EnrichmentCache,
    make_enrichment_cache_key,
)
from egregora.agents.shared.exceptions import (
    CacheDeserializationError,
    CachePayloadTypeError,
)


@pytest.fixture
def mock_cache_backend() -> MagicMock:
    """Fixture for a mocked CacheBackend."""
    return MagicMock()


@pytest.fixture
def enrichment_cache(mock_cache_backend: MagicMock) -> EnrichmentCache:
    """Fixture for an EnrichmentCache instance with a mocked backend."""
    return EnrichmentCache(backend=mock_cache_backend)


def test_make_enrichment_cache_key_is_stable():
    """Test that the cache key generation is deterministic."""
    key1 = make_enrichment_cache_key(kind="test", identifier="123")
    key2 = make_enrichment_cache_key(kind="test", identifier="123")
    assert key1 == key2


def test_make_enrichment_cache_key_is_sensitive_to_version():
    """Test that changing the version changes the key."""
    key1 = make_enrichment_cache_key(kind="test", identifier="123", version="v1")
    key2 = make_enrichment_cache_key(kind="test", identifier="123", version="v2")
    assert key1 != key2


def test_enrichment_cache_load_success(enrichment_cache: EnrichmentCache, mock_cache_backend: MagicMock):
    """Test successful loading of a valid cache entry."""
    mock_cache_backend.get.return_value = {"data": "test"}
    result = enrichment_cache.load("some_key")
    assert result == {"data": "test"}
    mock_cache_backend.get.assert_called_once_with("some_key")


def test_enrichment_cache_load_deserialization_error(
    enrichment_cache: EnrichmentCache, mock_cache_backend: MagicMock
):
    """Test handling of a deserialization error."""
    mock_cache_backend.get.side_effect = json.JSONDecodeError("err", "doc", 0)
    with pytest.raises(CacheDeserializationError):
        enrichment_cache.load("bad_key")
    mock_cache_backend.delete.assert_called_once_with("bad_key")


def test_enrichment_cache_load_payload_type_error(
    enrichment_cache: EnrichmentCache, mock_cache_backend: MagicMock
):
    """Test handling of an unexpected payload type."""
    mock_cache_backend.get.return_value = "not_a_dict"
    with pytest.raises(CachePayloadTypeError):
        enrichment_cache.load("wrong_type_key")
    mock_cache_backend.delete.assert_called_once_with("wrong_type_key")


def test_enrichment_cache_store(enrichment_cache: EnrichmentCache, mock_cache_backend: MagicMock):
    """Test storing a payload in the cache."""
    payload = {"data": "value"}
    enrichment_cache.store("my_key", payload)
    mock_cache_backend.set.assert_called_once_with("my_key", payload, expire=None)


def test_enrichment_cache_delete(enrichment_cache: EnrichmentCache, mock_cache_backend: MagicMock):
    """Test deleting an entry from the cache."""
    enrichment_cache.delete("my_key")
    mock_cache_backend.delete.assert_called_once_with("my_key")


def test_enrichment_cache_close(enrichment_cache: EnrichmentCache, mock_cache_backend: MagicMock):
    """Test closing the cache backend."""
    enrichment_cache.close()
    mock_cache_backend.close.assert_called_once()
