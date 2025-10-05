from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.cache import (
    ISO_FORMAT,
    cache_key_for_url,
    cleanup_enrichment_cache,
    create_enrichment_cache,
    get_enrichment_stats,
    has_enrichment,
    load_enrichment,
    store_enrichment,
)


def _build_analysis(model: str = "gemini-test") -> dict[str, object]:
    timestamp = datetime.now(timezone.utc).strftime(ISO_FORMAT)
    return {
        "model": model,
        "analyzed_at": timestamp,
        "enrichment": {
            "summary": "Resumo de teste",
            "key_points": ["um", "dois"],
            "tone": "informativo",
            "relevance": 4,
            "raw_response": "{}",
        },
        "context": {
            "message": "12:00 - Alice: veja o link",
            "messages_before": [],
            "messages_after": [],
            "sender": "Alice",
            "timestamp": "12:00",
            "date": "2024-01-01",
        },
        "metadata": {
            "domain": "example.com",
            "extracted_at": timestamp,
        },
        "version": "1.0",
    }


def test_cache_key_normalizes_urls() -> None:
    url_a = "https://Example.com/path/?b=2&a=1"
    url_b = "https://example.com/path?a=1&b=2"
    url_c = "https://example.com/other"

    uuid_a = cache_key_for_url(url_a)
    uuid_b = cache_key_for_url(url_b)
    uuid_c = cache_key_for_url(url_c)

    assert uuid_a == uuid_b
    assert uuid_a != uuid_c


def test_set_and_get_roundtrip(tmp_path: Path) -> None:
    cache = create_enrichment_cache(tmp_path / "cache")
    url = "https://example.com/artigo"
    payload = _build_analysis()

    assert load_enrichment(cache, "https://example.com/novo") is None

    stored = store_enrichment(cache, url, payload)
    assert stored["enrichment"]["summary"] == "Resumo de teste"

    cached = load_enrichment(cache, url)
    assert cached is not None
    assert cached["enrichment"]["relevance"] == 4

    stats = get_enrichment_stats(cache)
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1
    assert pytest.approx(stats["cache_hit_rate"], rel=1e-3) == 0.5
    assert stats["total_entries"] == 1


def test_cleanup_removes_old_entries(tmp_path: Path) -> None:
    cache = create_enrichment_cache(tmp_path / "cache")
    url = "https://example.com/desatualizado"
    store_enrichment(cache, url, _build_analysis())

    key = cache_key_for_url(url)
    entry = cache.get(key)
    assert entry is not None
    entry["last_used"] = (
        datetime.now(timezone.utc) - timedelta(days=120)
    ).strftime(ISO_FORMAT)
    cache.set(key, entry)

    removed = cleanup_enrichment_cache(cache, 90)
    assert removed == 1
    assert not has_enrichment(cache, url)


def test_missing_entry_counts_as_miss(tmp_path: Path) -> None:
    cache = create_enrichment_cache(tmp_path / "cache")
    assert load_enrichment(cache, "https://example.com/absent") is None
    stats = get_enrichment_stats(cache)
    assert stats["cache_hits"] == 0
    assert stats["cache_misses"] == 1
