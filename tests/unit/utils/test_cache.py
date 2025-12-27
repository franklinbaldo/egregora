import json
from unittest.mock import MagicMock

import pytest

from egregora.utils.cache import EnrichmentCache
from egregora.utils.exceptions import CacheDeserializationError


@pytest.fixture
def mock_backend():
    """Provides a MagicMock for the CacheBackend."""
    return MagicMock()


@pytest.fixture
def enrichment_cache(mock_backend):
    """Provides an EnrichmentCache instance with a mocked backend."""
    return EnrichmentCache(backend=mock_backend)


def test_load_returns_none_if_key_not_found(enrichment_cache, mock_backend):
    """Test that load returns None when a key is not in the cache."""
    mock_backend.get.return_value = None
    assert enrichment_cache.load("nonexistent_key") is None
    mock_backend.get.assert_called_once_with("nonexistent_key")


def test_load_returns_dict_on_success(enrichment_cache, mock_backend):
    """Test that load returns a dictionary for a valid cache entry."""
    expected_payload = {"data": "some_value"}
    mock_backend.get.return_value = expected_payload
    assert enrichment_cache.load("valid_key") == expected_payload
    mock_backend.get.assert_called_once_with("valid_key")


def test_load_handles_json_decode_error(enrichment_cache, mock_backend):
    """Test that load handles JSONDecodeError and raises CacheDeserializationError."""
    mock_backend.get.side_effect = json.JSONDecodeError("msg", "doc", 0)
    with pytest.raises(CacheDeserializationError):
        enrichment_cache.load("corrupt_key")
    mock_backend.delete.assert_called_once_with("corrupt_key")


def test_load_handles_type_error(enrichment_cache, mock_backend):
    """Test that load handles TypeError and raises CacheDeserializationError."""
    mock_backend.get.side_effect = TypeError("some type error")
    with pytest.raises(CacheDeserializationError):
        enrichment_cache.load("type_error_key")
    mock_backend.delete.assert_called_once_with("type_error_key")


def test_load_handles_value_error(enrichment_cache, mock_backend):
    """Test that load handles ValueError and raises CacheDeserializationError."""
    mock_backend.get.side_effect = ValueError("some value error")
    with pytest.raises(CacheDeserializationError):
        enrichment_cache.load("value_error_key")
    mock_backend.delete.assert_called_once_with("value_error_key")


def test_load_handles_non_dict_payload(enrichment_cache, mock_backend):
    """Test that load returns None and deletes the key for a non-dict payload."""
    mock_backend.get.return_value = "not a dictionary"
    assert enrichment_cache.load("non_dict_key") is None
    mock_backend.delete.assert_called_once_with("non_dict_key")


def test_store_calls_backend_set(enrichment_cache, mock_backend):
    """Test that store calls the backend's set method."""
    payload = {"data": "test"}
    enrichment_cache.store("test_key", payload)
    mock_backend.set.assert_called_once_with("test_key", payload, expire=None)


def test_delete_calls_backend_delete(enrichment_cache, mock_backend):
    """Test that delete calls the backend's delete method."""
    enrichment_cache.delete("test_key")
    mock_backend.delete.assert_called_once_with("test_key")


def test_close_calls_backend_close(enrichment_cache, mock_backend):
    """Test that close calls the backend's close method."""
    enrichment_cache.close()
    mock_backend.close.assert_called_once()
