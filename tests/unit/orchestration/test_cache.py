"""Tests for the orchestration cache."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.orchestration.cache import CacheTier, PipelineCache


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for cache."""
    return tmp_path / "cache"


def test_pipeline_cache_initialization(temp_cache_dir: Path):
    """Test that PipelineCache initializes its tiers correctly."""
    with patch("diskcache.Cache") as mock_diskcache, patch(
        "egregora.orchestration.cache.EnrichmentCache"
    ) as mock_enrichment_cache:
        cache = PipelineCache(temp_cache_dir)

        assert cache.base_dir == temp_cache_dir
        assert temp_cache_dir.exists()

        # Check that cache tiers were initialized
        mock_enrichment_cache.assert_called_once()
        # The backend for enrichment also creates a diskcache instance
        assert mock_diskcache.call_count == 3
        mock_diskcache.assert_any_call(str(temp_cache_dir / "rag"))
        mock_diskcache.assert_any_call(str(temp_cache_dir / "writer"))


@pytest.mark.parametrize(
    ("refresh_tiers", "tier_to_check", "expected"),
    [
        ({"all"}, CacheTier.RAG, True),
        ({"rag", "writer"}, CacheTier.RAG, True),
        ({"rag", "writer"}, CacheTier.WRITER, True),
        ({"writer"}, CacheTier.RAG, False),
        (set(), CacheTier.ENRICHMENT, False),
        (None, CacheTier.WRITER, False),
    ],
)
def test_pipeline_cache_should_refresh(
    temp_cache_dir: Path, refresh_tiers: set[str] | None, tier_to_check: CacheTier, expected: bool
):
    """Test the should_refresh logic."""
    cache = PipelineCache(temp_cache_dir, refresh_tiers=refresh_tiers)
    assert cache.should_refresh(tier_to_check) is expected


def test_pipeline_cache_close(temp_cache_dir: Path):
    """Test that closing the PipelineCache closes all tier caches."""
    with patch("diskcache.Cache") as mock_diskcache, patch(
        "egregora.orchestration.cache.EnrichmentCache"
    ) as mock_enrichment_cache:
        # Instantiate mocks for the tier caches
        mock_enrichment_disk_cache = MagicMock()
        mock_rag_cache = MagicMock()
        mock_writer_cache = MagicMock()
        mock_diskcache.side_effect = [
            mock_enrichment_disk_cache,
            mock_rag_cache,
            mock_writer_cache,
        ]

        mock_enrichment_cache_instance = MagicMock()
        mock_enrichment_cache.return_value = mock_enrichment_cache_instance

        cache = PipelineCache(temp_cache_dir)
        cache.close()

        # Assert that close was called on each tier's cache
        mock_enrichment_cache_instance.close.assert_called_once()
        mock_rag_cache.close.assert_called_once()
        mock_writer_cache.close.assert_called_once()
