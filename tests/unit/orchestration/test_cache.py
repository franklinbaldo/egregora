from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from egregora.orchestration.cache import CacheTier, PipelineCache
from egregora.orchestration.exceptions import CacheKeyNotFoundError


def test_pipeline_cache_initialization():
    """Verify that the PipelineCache initializes its tiers correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        cache = PipelineCache(base_dir=cache_dir)
        assert cache.base_dir == cache_dir
        assert (cache_dir / "enrichment").exists()
        assert (cache_dir / "rag").exists()
        assert (cache_dir / "writer").exists()
        cache.close()


def test_pipeline_cache_refresh_tiers():
    """Test the should_refresh method for different tiers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)

        # Test refreshing a single tier
        cache = PipelineCache(base_dir=cache_dir, refresh_tiers={"rag"})
        assert not cache.should_refresh(CacheTier.ENRICHMENT)
        assert cache.should_refresh(CacheTier.RAG)
        assert not cache.should_refresh(CacheTier.WRITER)
        cache.close()

        # Test refreshing all tiers
        cache_all = PipelineCache(base_dir=cache_dir, refresh_tiers={"all"})
        assert cache_all.should_refresh(CacheTier.ENRICHMENT)
        assert cache_all.should_refresh(CacheTier.RAG)
        assert cache_all.should_refresh(CacheTier.WRITER)
        cache_all.close()

        # Test no refresh tiers
        cache_none = PipelineCache(base_dir=cache_dir)
        assert not cache_none.should_refresh(CacheTier.ENRICHMENT)
        assert not cache_none.should_refresh(CacheTier.RAG)
        assert not cache_none.should_refresh(CacheTier.WRITER)
        cache_none.close()


def test_enrichment_cache_operations():
    """Test store, load, and delete operations for the EnrichmentCache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        cache = PipelineCache(base_dir=cache_dir)

        key = "test_key"
        payload = {"data": "test_data"}

        # Store and load
        cache.enrichment.store(key, payload)
        loaded_payload = cache.enrichment.load(key)
        assert loaded_payload == payload

        # Delete
        cache.enrichment.delete(key)
        with pytest.raises(CacheKeyNotFoundError):
            cache.enrichment.load(key)

        cache.close()
