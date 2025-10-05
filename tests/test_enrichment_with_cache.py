from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.cache_manager import CacheManager
from egregora.config import EnrichmentConfig
from egregora.enrichment import AnalysisResult, ContentEnricher


@pytest.fixture()
def cache_manager(tmp_path: Path) -> CacheManager:
    return CacheManager(tmp_path / "cache")


async def _fake_analysis(_: object, __: object) -> AnalysisResult:
    return AnalysisResult(
        summary="Conteúdo resumido",
        key_points=["a", "b"],
        tone="informativo",
        relevance=5,
        raw_response="{}",
    )


def _build_transcripts() -> list[tuple[date, str]]:
    transcript = "12:00 - Alice: Confira https://example.com/artigo incrivel"
    return [(date(2024, 1, 1), transcript)]


def test_enrichment_uses_cache_on_subsequent_runs(
    cache_manager: CacheManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = EnrichmentConfig()
    config.max_links = 5
    enricher = ContentEnricher(config, cache_manager=cache_manager)

    monkeypatch.setattr(ContentEnricher, "_analyze_reference", staticmethod(_fake_analysis))

    result_first = asyncio.run(enricher.enrich(_build_transcripts()))
    assert result_first.items
    extracted_url = result_first.items[0].reference.url
    assert extracted_url is not None
    assert cache_manager.exists(extracted_url)

    def _fail(*_: object, **__: object) -> None:
        raise AssertionError("Cache was not used")

    monkeypatch.setattr(ContentEnricher, "_analyze_reference", staticmethod(_fail))

    result_second = asyncio.run(enricher.enrich(_build_transcripts()))
    assert result_second.items
    assert result_second.items[0].analysis is not None
    assert result_second.items[0].analysis.summary == "Conteúdo resumido"

    stats = cache_manager.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1