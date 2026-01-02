from __future__ import annotations

from unittest.mock import Mock

import pytest

from egregora.utils.cache import EnrichmentCache
from egregora.utils.exceptions import CacheDeserializationError, CachePayloadTypeError


@pytest.fixture
def mock_backend():
    """Fixture for a mocked CacheBackend."""
    return Mock()


@pytest.fixture
def enrichment_cache(mock_backend):
    """Fixture for an EnrichmentCache instance with a mocked backend."""
    return EnrichmentCache(backend=mock_backend)


def test_enrichment_cache_store(enrichment_cache, mock_backend):
    """Test that store calls the backend's set method correctly."""
    key = "test_key"
    payload = {"data": "test_payload"}
    enrichment_cache.store(key, payload)
    mock_backend.set.assert_called_once_with(key, payload, expire=None)


def test_enrichment_cache_load_success(enrichment_cache, mock_backend):
    """Test successful loading of a cached payload."""
    key = "test_key"
    payload = {"data": "test_payload"}
    mock_backend.get.return_value = payload

    result = enrichment_cache.load(key)

    mock_backend.get.assert_called_once_with(key)
    assert result == payload


def test_enrichment_cache_load_deserialization_error(enrichment_cache, mock_backend):
    """Test that a DeserializationError is raised for invalid JSON."""
    key = "test_key"
    mock_backend.get.side_effect = TypeError("Invalid data")

    with pytest.raises(CacheDeserializationError):
        enrichment_cache.load(key)

    mock_backend.get.assert_called_once_with(key)
    mock_backend.delete.assert_called_once_with(key)


def test_enrichment_cache_load_payload_type_error(enrichment_cache, mock_backend):
    """Test that a PayloadTypeError is raised for non-dict payloads."""
    key = "test_key"
    mock_backend.get.return_value = "not a dict"

    with pytest.raises(CachePayloadTypeError):
        enrichment_cache.load(key)

    mock_backend.get.assert_called_once_with(key)
    mock_backend.delete.assert_called_once_with(key)


def test_enrichment_cache_delete(enrichment_cache, mock_backend):
    """Test that delete calls the backend's delete method."""
    key = "test_key"
    enrichment_cache.delete(key)
    mock_backend.delete.assert_called_once_with(key)


def test_enrichment_cache_close(enrichment_cache, mock_backend):
    """Test that close calls the backend's close method."""
    enrichment_cache.close()
    mock_backend.close.assert_called_once()
