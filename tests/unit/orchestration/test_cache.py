from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.orchestration.cache import (
    CacheTier,
    EnrichmentCache,
    PipelineCache,
    make_enrichment_cache_key,
)
from egregora.utils.cache_backend import CacheBackend
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


def test_pipeline_cache_initialization(tmp_path: Path):
    """Tests that PipelineCache initializes its tiers correctly."""
    cache = PipelineCache(base_dir=tmp_path)
    assert (tmp_path / "enrichment").is_dir()
    assert (tmp_path / "rag").is_dir()
    assert (tmp_path / "writer").is_dir()
    assert isinstance(cache.enrichment, EnrichmentCache)
    # The underlying cache objects in diskcache are created on demand,
    # but the directories should exist. We can check the type of the attribute.
    assert hasattr(cache.rag, "close")  # Check if it's a cache-like object
    assert hasattr(cache.writer, "close")
    cache.close()


@pytest.mark.parametrize(
    ("refresh_tiers", "tier_to_check", "expected"),
    [
        ({"all"}, CacheTier.ENRICHMENT, True),
        ({"all"}, CacheTier.RAG, True),
        ({"enrichment"}, CacheTier.ENRICHMENT, True),
        ({"rag", "writer"}, CacheTier.WRITER, True),
        ({"enrichment"}, CacheTier.RAG, False),
        (set(), CacheTier.ENRICHMENT, False),
        (None, CacheTier.RAG, False),
    ],
)
def test_pipeline_cache_should_refresh(
    tmp_path: Path,
    refresh_tiers: set[str] | None,
    tier_to_check: CacheTier,
    *,
    expected: bool,
):
    """Tests the logic for checking if a tier should be refreshed."""
    cache = PipelineCache(base_dir=tmp_path, refresh_tiers=refresh_tiers)
    assert cache.should_refresh(tier_to_check) is expected
    cache.close()


def test_pipeline_cache_close(tmp_path: Path):
    """Tests that closing the PipelineCache closes all its tiers."""
    with patch("diskcache.Cache") as mock_diskcache:
        # diskcache.Cache is instantiated 3 times in PipelineCache.__init__:
        # 1. Inside DiskCacheBackend for the enrichment cache.
        # 2. For the rag cache.
        # 3. For the writer cache.
        mock_enrichment_disk_cache = MagicMock()
        mock_rag_disk_cache = MagicMock()
        mock_writer_disk_cache = MagicMock()
        mock_diskcache.side_effect = [
            mock_enrichment_disk_cache,
            mock_rag_disk_cache,
            mock_writer_disk_cache,
        ]

        # This will call diskcache.Cache 3 times, consuming the side_effect mocks
        cache = PipelineCache(base_dir=tmp_path)

        # Call the close method
        cache.close()

        # PipelineCache.close() calls close() on each of its cache attributes.
        # For enrichment, it's EnrichmentCache -> DiskCacheBackend -> diskcache.Cache.
        # For rag/writer, it's a direct diskcache.Cache.
        mock_enrichment_disk_cache.close.assert_called_once()
        mock_rag_disk_cache.close.assert_called_once()
        mock_writer_disk_cache.close.assert_called_once()


def test_enrichment_cache_load_payload_type_error(mock_backend):
    """Tests that incorrect payload types are handled gracefully."""
    mock_backend.get.return_value = "this is not a dict"
    cache = EnrichmentCache(backend=mock_backend)

    with pytest.raises(CachePayloadTypeError):
        cache.load("test_key")

    mock_backend.get.assert_called_once_with("test_key")
    mock_backend.delete.assert_called_once_with("test_key")
