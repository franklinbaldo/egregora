import json
import shutil
import tempfile
from pathlib import Path

import pytest

from egregora.cache import CacheTier, PipelineCache, make_enrichment_cache_key
from egregora.cache.exceptions import (
    CacheDeserializationError,
    CachePayloadTypeError,
)


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for the cache."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


def test_enrichment_persistence(temp_cache_dir):
    """Verify that enrichment cache persists to disk."""
    cache = PipelineCache(temp_cache_dir)
    key = make_enrichment_cache_key(kind="url", identifier="http://example.com")
    payload = {"markdown": "Cached content", "slug": "cached-slug", "type": "url"}

    # Store in cache
    cache.enrichment.store(key, payload)
    cache.close()

    # Re-open cache
    new_cache = PipelineCache(temp_cache_dir)
    loaded = new_cache.enrichment.load(key)

    assert loaded is not None
    assert loaded["markdown"] == "Cached content"
    new_cache.close()


def test_writer_cache_persistence(temp_cache_dir):
    """Verify that writer cache persists to disk."""
    cache = PipelineCache(temp_cache_dir)
    signature = "test-signature-123"
    result = {"posts": ["post1"], "profiles": ["profile1"]}

    # Store in cache
    cache.writer.set(signature, result)
    cache.close()

    # Re-open cache
    new_cache = PipelineCache(temp_cache_dir)
    loaded = new_cache.writer.get(signature)

    assert loaded is not None
    assert loaded["posts"] == ["post1"]
    new_cache.close()


def test_force_refresh(temp_cache_dir):
    """Verify that refresh='all' ignores existing cache entries."""
    # 1. Populate cache
    cache = PipelineCache(temp_cache_dir)
    key = "test-key"
    cache.writer.set(key, "old-value")
    cache.close()

    # 2. Open with refresh="all"
    refresh_cache = PipelineCache(temp_cache_dir, refresh_tiers={"all"})

    # Should ignore existing value (conceptually, though diskcache might still return it if we ask directly,
    # the wrapper logic in write_pipeline uses should_refresh to skip checking).
    # So we test should_refresh here.
    assert refresh_cache.should_refresh(CacheTier.WRITER)

    # 3. Open with specific tier refresh
    writer_refresh_cache = PipelineCache(temp_cache_dir, refresh_tiers={"writer"})
    assert writer_refresh_cache.should_refresh(CacheTier.WRITER)

    # 4. Open with enrichment tier refresh
    enrichment_refresh_cache = PipelineCache(temp_cache_dir, refresh_tiers={"enrichment"})
    assert enrichment_refresh_cache.should_refresh(CacheTier.ENRICHMENT)
    assert not enrichment_refresh_cache.should_refresh(CacheTier.WRITER)

    writer_refresh_cache.close()
    enrichment_refresh_cache.close()


def test_enrichment_deserialization_error(temp_cache_dir, mocker):
    """Verify deserialization errors are caught and the key is deleted."""
    cache = PipelineCache(temp_cache_dir)
    key = "corrupted-key"

    # Mock the backend's get method to simulate a JSON decoding error
    mocker.patch.object(
        cache.enrichment.backend,
        "get",
        side_effect=json.JSONDecodeError("mock error", "", 0),
    )
    # Spy on the delete method to ensure it's called
    delete_spy = mocker.spy(cache.enrichment.backend, "delete")

    # The load method should catch the JSON error, raise our custom exception,
    # and delete the corrupted key.
    with pytest.raises(CacheDeserializationError):
        cache.enrichment.load(key)

    delete_spy.assert_called_once_with(key)
    cache.close()


def test_rag_cache_persistence(temp_cache_dir):
    """Verify that RAG cache persists to disk."""
    cache = PipelineCache(temp_cache_dir)
    key = "test-rag-key"
    value = {"embeddings": [0.1, 0.2, 0.3], "metadata": {"source": "test.txt"}}

    # Store in cache
    cache.rag.set(key, value)
    cache.close()

    # Re-open cache
    new_cache = PipelineCache(temp_cache_dir)
    loaded = new_cache.rag.get(key)

    assert loaded is not None
    assert loaded["embeddings"] == [0.1, 0.2, 0.3]
    new_cache.close()


def test_enrichment_invalid_payload_type(temp_cache_dir, mocker):
    """Verify that a non-dict payload is handled gracefully."""
    cache = PipelineCache(temp_cache_dir)
    key = "invalid-payload-key"

    # Store a non-dictionary value
    cache.enrichment.backend.set(key, "this is a string, not a dict")

    # Spy on the delete method
    delete_spy = mocker.spy(cache.enrichment.backend, "delete")

    # The load method should raise CachePayloadTypeError and delete the invalid entry
    with pytest.raises(CachePayloadTypeError):
        cache.enrichment.load(key)

    delete_spy.assert_called_once_with(key)
    cache.close()
