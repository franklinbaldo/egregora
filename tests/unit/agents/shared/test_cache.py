from unittest.mock import MagicMock

import pytest

from egregora.agents.shared.cache import (
    EnrichmentCache,
    make_enrichment_cache_key,
)
from egregora.infra.cache import CacheBackend
from egregora.utils.exceptions import (
    CacheDeserializationError,
    CachePayloadTypeError,
)


@pytest.fixture
def mock_backend() -> MagicMock:
    """Provides a mocked CacheBackend."""
    return MagicMock(spec=CacheBackend)


def test_make_enrichment_cache_key_stability():
    """Ensures the cache key generation is deterministic."""
    key1 = make_enrichment_cache_key(kind="url", identifier="http://example.com", version="v1")
    key2 = make_enrichment_cache_key(kind="url", identifier="http://example.com", version="v1")
    assert key1 == key2
    assert key1 == "6a46a3d2a7e7d0eab5bce3b9cd50d1b3b578a9d3f172cffee8cac3c9eea61b95"


def test_make_enrichment_cache_key_uniqueness():
    """Ensures different inputs produce different cache keys."""
    key1 = make_enrichment_cache_key(kind="url", identifier="http://example.com")
    key2 = make_enrichment_cache_key(kind="media", identifier="http://example.com")
    key3 = make_enrichment_cache_key(kind="url", identifier="http://example.org")
    key4 = make_enrichment_cache_key(kind="url", identifier="http://example.com", version="v3")
    assert len({key1, key2, key3, key4}) == 4


def test_enrichment_cache_load_success(mock_backend):
    """Tests successful retrieval of a valid cache entry."""
    mock_backend.get.return_value = {"payload": "data"}
    cache = EnrichmentCache(backend=mock_backend)
    data = cache.load("test_key")
    mock_backend.get.assert_called_once_with("test_key")
    assert data == {"payload": "data"}


def test_enrichment_cache_store(mock_backend):
    """Tests storing a payload in the cache."""
    cache = EnrichmentCache(backend=mock_backend)
    payload = {"payload": "data"}
    cache.store("test_key", payload)
    mock_backend.set.assert_called_once_with("test_key", payload, expire=None)


def test_enrichment_cache_delete(mock_backend):
    """Tests deleting an entry from the cache."""
    cache = EnrichmentCache(backend=mock_backend)
    cache.delete("test_key")
    mock_backend.delete.assert_called_once_with("test_key")


def test_enrichment_cache_close(mock_backend):
    """Tests that the close method is passed to the backend."""
    cache = EnrichmentCache(backend=mock_backend)
    cache.close()
    mock_backend.close.assert_called_once()


def test_enrichment_cache_load_deserialization_error(mock_backend):
    """Tests that deserialization errors are handled gracefully."""
    mock_backend.get.side_effect = TypeError("Invalid JSON")
    cache = EnrichmentCache(backend=mock_backend)

    with pytest.raises(CacheDeserializationError):
        cache.load("test_key")

    mock_backend.get.assert_called_once_with("test_key")
    mock_backend.delete.assert_called_once_with("test_key")


def test_enrichment_cache_load_payload_type_error(mock_backend):
    """Tests that incorrect payload types are handled gracefully."""
    mock_backend.get.return_value = "this is not a dict"
    cache = EnrichmentCache(backend=mock_backend)

    with pytest.raises(CachePayloadTypeError):
        cache.load("test_key")

    mock_backend.get.assert_called_once_with("test_key")
    mock_backend.delete.assert_called_once_with("test_key")
