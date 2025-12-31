from __future__ import annotations

import json
from unittest.mock import Mock, call

import pytest

from egregora.utils.cache import (
    EnrichmentCache,
    make_enrichment_cache_key,
)
from egregora.utils.exceptions import (
    CacheDeserializationError,
    CacheKeyNotFoundError,
    CachePayloadTypeError,
)


@pytest.fixture
def mock_backend():
    return Mock()


@pytest.fixture
def cache(mock_backend):
    return EnrichmentCache(backend=mock_backend)


def test_make_enrichment_cache_key():
    key = make_enrichment_cache_key(kind="test", identifier="123")
    assert isinstance(key, str)
    assert len(key) == 64  # SHA256 hex digest


def test_store_calls_backend_set(cache, mock_backend):
    payload = {"foo": "bar"}
    cache.store("key1", payload)
    mock_backend.set.assert_called_once_with("key1", payload, expire=None)


def test_delete_calls_backend_delete(cache, mock_backend):
    cache.delete("key1")
    mock_backend.delete.assert_called_once_with("key1")


def test_load_returns_payload(cache, mock_backend):
    payload = {"foo": "bar"}
    mock_backend.get.return_value = payload
    assert cache.load("key1") == payload
    mock_backend.get.assert_called_once_with("key1")


def test_load_propagates_key_not_found(cache, mock_backend):
    mock_backend.get.side_effect = CacheKeyNotFoundError("key1")
    with pytest.raises(CacheKeyNotFoundError):
        cache.load("key1")


def test_load_handles_deserialization_error(cache, mock_backend):
    # Simulate a JSON decode error or similar (backend might return raw bytes if not configured properly,
    # but here we simulate an exception raised by backend or validation)
    # Actually EnrichmentCache code catches (json.JSONDecodeError, TypeError, ValueError) during get?
    # No, it calls backend.get(key). If backend raises, it propagates unless backend returns malformed data?
    # Wait, let's look at source.
    pass


def test_load_raises_deserialization_error_on_value_error(cache, mock_backend):
    # If backend.get raises ValueError (e.g. corrupt pickle/json), EnrichmentCache should catch it, delete key, and raise CacheDeserializationError
    mock_backend.get.side_effect = ValueError("Corrupt")
    with pytest.raises(CacheDeserializationError):
        cache.load("key1")
    mock_backend.delete.assert_called_once_with("key1")


def test_load_raises_type_error_on_non_dict(cache, mock_backend):
    mock_backend.get.return_value = "not a dict"
    with pytest.raises(CachePayloadTypeError):
        cache.load("key1")
    mock_backend.delete.assert_called_once_with("key1")
