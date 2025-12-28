from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import diskcache
import pytest

from egregora.utils.cache import (
    CacheTier,
    DiskCacheBackend,
    EnrichmentCache,
    PipelineCache,
    make_enrichment_cache_key,
)
from egregora.utils.exceptions import (
    CacheDeserializationError,
    CachePayloadTypeError,
)


def test_enrichment_cache_load_raises_on_invalid_payload_type() -> None:
    """Test that EnrichmentCache.load raises CachePayloadTypeError for non-dict payloads."""
    # Arrange
    mock_backend = Mock()
    key = "test_key"
    invalid_payload = ["this", "is", "a", "list"]
    mock_backend.get.return_value = invalid_payload

    cache = EnrichmentCache(backend=mock_backend)

    # Act & Assert
    with pytest.raises(CachePayloadTypeError) as excinfo:
        cache.load(key)

    # Assert that the exception has the correct context
    assert excinfo.value.key == key
    assert excinfo.value.payload_type is type(invalid_payload)
    mock_backend.delete.assert_called_once_with(key)


def test_enrichment_cache_load_success() -> None:
    """Test that EnrichmentCache.load returns a valid payload."""
    # Arrange
    mock_backend = Mock()
    key = "test_key"
    payload = {"data": "some_data"}
    mock_backend.get.return_value = payload

    cache = EnrichmentCache(backend=mock_backend)

    # Act
    result = cache.load(key)

    # Assert
    assert result == payload
    mock_backend.get.assert_called_once_with(key)


def test_enrichment_cache_load_miss() -> None:
    """Test that EnrichmentCache.load returns None for a cache miss."""
    # Arrange
    mock_backend = Mock()
    key = "test_key"
    mock_backend.get.return_value = None

    cache = EnrichmentCache(backend=mock_backend)

    # Act
    result = cache.load(key)

    # Assert
    assert result is None
    mock_backend.get.assert_called_once_with(key)


def test_enrichment_cache_load_raises_on_deserialization_error() -> None:
    """Test that EnrichmentCache.load raises CacheDeserializationError on backend error."""
    # Arrange
    mock_backend = Mock()
    key = "test_key"
    mock_backend.get.side_effect = json.JSONDecodeError("msg", "doc", 0)

    cache = EnrichmentCache(backend=mock_backend)

    # Act & Assert
    with pytest.raises(CacheDeserializationError) as excinfo:
        cache.load(key)

    assert excinfo.value.key == key
    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)
    mock_backend.delete.assert_called_once_with(key)


def test_enrichment_cache_store_calls_backend() -> None:
    """Test that EnrichmentCache.store calls the backend's set method."""
    # Arrange
    mock_backend = Mock()
    cache = EnrichmentCache(backend=mock_backend)
    key = "test_key"
    payload = {"data": "test"}

    # Act
    cache.store(key, payload)

    # Assert
    mock_backend.set.assert_called_once_with(key, payload, expire=None)


def test_enrichment_cache_delete_calls_backend() -> None:
    """Test that EnrichmentCache.delete calls the backend's delete method."""
    # Arrange
    mock_backend = Mock()
    cache = EnrichmentCache(backend=mock_backend)
    key = "test_key"

    # Act
    cache.delete(key)

    # Assert
    mock_backend.delete.assert_called_once_with(key)


def test_enrichment_cache_close_calls_backend() -> None:
    """Test that EnrichmentCache.close calls the backend's close method."""
    # Arrange
    mock_backend = Mock()
    cache = EnrichmentCache(backend=mock_backend)

    # Act
    cache.close()

    # Assert
    mock_backend.close.assert_called_once()


def test_disk_cache_backend_operations(tmp_path: Path) -> None:
    """Test basic get, set, and delete operations for DiskCacheBackend."""
    # Arrange
    cache_dir = tmp_path / "test_cache"
    backend = DiskCacheBackend(directory=cache_dir)
    key = "my_key"
    value = {"message": "hello"}

    # Act & Assert: Set and Get
    backend.set(key, value)
    retrieved = backend.get(key)
    assert retrieved == value

    # Act & Assert: Delete
    backend.delete(key)
    assert backend.get(key) is None

    # Act & Assert: Dict-style access
    backend[key] = value
    assert backend[key] == value
    del backend[key]
    assert backend.get(key) is None

    backend.close()


def test_pipeline_cache_initialization(tmp_path: Path) -> None:
    """Test that PipelineCache initializes tiers correctly."""
    # Arrange
    base_dir = tmp_path / "pipeline_cache"

    # Act
    pipeline_cache = PipelineCache(base_dir=base_dir)

    # Assert
    assert pipeline_cache.base_dir == base_dir
    assert isinstance(pipeline_cache.enrichment, EnrichmentCache)
    assert isinstance(pipeline_cache.rag, diskcache.Cache)
    assert isinstance(pipeline_cache.writer, diskcache.Cache)
    assert (base_dir / "enrichment").exists()
    assert (base_dir / "rag").exists()
    assert (base_dir / "writer").exists()

    pipeline_cache.close()


@pytest.mark.parametrize(
    ("refresh_tiers", "tier_to_check", "expected"),
    [
        ({"all"}, CacheTier.ENRICHMENT, True),
        ({"enrichment"}, CacheTier.ENRICHMENT, True),
        ({"rag"}, CacheTier.ENRICHMENT, False),
        (set(), CacheTier.WRITER, False),
        ({"enrichment", "writer"}, CacheTier.WRITER, True),
    ],
)
def test_pipeline_cache_should_refresh(
    tmp_path: Path,
    refresh_tiers: set[str],
    tier_to_check: CacheTier,
    expected: bool,
) -> None:
    """Test the should_refresh logic for PipelineCache."""
    # Arrange
    pipeline_cache = PipelineCache(base_dir=tmp_path, refresh_tiers=refresh_tiers)

    # Act
    result = pipeline_cache.should_refresh(tier_to_check)

    # Assert
    assert result is expected

    pipeline_cache.close()


def test_make_enrichment_cache_key_is_stable() -> None:
    """Test that the enrichment cache key function is stable."""
    # Arrange
    kind = "url"
    identifier = "https://example.com"
    version = "v1"

    # Act
    key1 = make_enrichment_cache_key(kind=kind, identifier=identifier, version=version)
    key2 = make_enrichment_cache_key(kind=kind, identifier=identifier, version=version)

    # Assert
    assert key1 == key2
    assert isinstance(key1, str)
