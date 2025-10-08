from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import polars as pl

from egregora.cache_manager import CacheManager
from egregora.config import EnrichmentConfig
from egregora.enrichment import AnalysisResult, ContentEnricher


@pytest.fixture()
def cache_manager(tmp_path: Path) -> CacheManager:
    return CacheManager(tmp_path / "cache", size_limit_mb=1)


async def _fake_analysis(self, reference, *, client=None) -> AnalysisResult:
    return AnalysisResult(
        summary="Conteúdo resumido",
        topics=["a", "b"],
        actions=[],
        relevance=5,
        raw_response="{}",
    )


def _build_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "date": [date(2024, 1, 1)],
            "timestamp": [datetime(2024, 1, 1, 12, 0)],
            "author": ["Alice"],
            "message": ["Confira https://example.com/artigo incrivel"],
        }
    )


def test_enrichment_uses_cache_on_subsequent_runs(
    cache_manager: CacheManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = EnrichmentConfig()
    config.max_links = 5
    enricher = ContentEnricher(config, cache_manager=cache_manager)

    monkeypatch.setattr(ContentEnricher, "_analyze_reference", _fake_analysis, raising=True)

    frame = _build_frame()
    result_first = asyncio.run(enricher.enrich_dataframe(frame, client=None))
    assert result_first.items
    extracted_url = result_first.items[0].reference.url
    assert extracted_url is not None
    assert cache_manager.exists(extracted_url)

    async def _fail(self, *args, **kwargs) -> None:
        raise AssertionError("Cache was not used")

    monkeypatch.setattr(ContentEnricher, "_analyze_reference", _fail, raising=True)

    result_second = asyncio.run(enricher.enrich_dataframe(frame, client=None))
    assert result_second.items
    assert result_second.items[0].analysis is not None
    assert result_second.items[0].analysis.summary == "Conteúdo resumido"

    stats = cache_manager.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1
