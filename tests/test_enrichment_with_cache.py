from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diskcache import Cache

from egregora.cache import (
    create_enrichment_cache,
    get_enrichment_stats,
    has_enrichment,
)
from egregora.config import EnrichmentConfig
from egregora.enrichment import AnalysisResult, EnrichmentWorker


@pytest.fixture()
def enrichment_cache(tmp_path: Path) -> Cache:
    return create_enrichment_cache(tmp_path / "cache")


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
    enrichment_cache: Cache, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = EnrichmentConfig()
    config.max_links = 5
    enricher = EnrichmentWorker(config, cache=enrichment_cache)

    monkeypatch.setattr(EnrichmentWorker, "_analyze_reference", staticmethod(_fake_analysis))

    result_first = asyncio.run(enricher.enrich(_build_transcripts(), client=None))
    assert result_first.items
    extracted_url = result_first.items[0].reference.url
    assert extracted_url is not None
    assert has_enrichment(enrichment_cache, extracted_url)

    def _fail(*_: object, **__: object) -> None:
        raise AssertionError("Cache was not used")

    monkeypatch.setattr(EnrichmentWorker, "_analyze_reference", staticmethod(_fail))

    result_second = asyncio.run(enricher.enrich(_build_transcripts(), client=None))
    assert result_second.items
    assert result_second.items[0].analysis is not None
    assert result_second.items[0].analysis.summary == "Conteúdo resumido"

    stats = get_enrichment_stats(enrichment_cache)
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1
