import shutil
import tempfile
from pathlib import Path

import pytest

from egregora.utils.cache import PipelineCache, make_enrichment_cache_key


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
    cache.enrichment.set(key, payload)
    cache.close()

    # Re-open cache
    new_cache = PipelineCache(temp_cache_dir)
    loaded = new_cache.enrichment.get(key)

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
    assert refresh_cache.should_refresh("writer")

    # 3. Open with specific tier refresh
    writer_refresh_cache = PipelineCache(temp_cache_dir, refresh_tiers={"writer"})
    assert writer_refresh_cache.should_refresh("writer")

    # 4. Open with enrichment tier refresh
    enrichment_refresh_cache = PipelineCache(temp_cache_dir, refresh_tiers={"enrichment"})
    assert enrichment_refresh_cache.should_refresh("enrichment")
    assert not enrichment_refresh_cache.should_refresh("writer")

    writer_refresh_cache.close()
    enrichment_refresh_cache.close()
