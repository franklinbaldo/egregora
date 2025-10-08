from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.cache_manager import CacheManager

EXPECTED_RELEVANCE_SCORE = 4
EXPECTED_CACHE_HIT_RATE = 0.5


def _build_analysis(model: str = "gemini-test") -> dict[str, object]:
    timestamp = datetime.now(UTC).isoformat()
    return {
        "model": model,
        "analyzed_at": timestamp,
        "enrichment": {
            "summary": "Resumo de teste",
            "topics": ["um", "dois"],
            "actions": [
                {
                    "description": "Compartilhar com a equipe",
                    "owner": "Alice",
                }
            ],
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


def test_generate_uuid_normalizes_urls(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache", size_limit_mb=1)
    url_a = "https://Example.com/path/?b=2&a=1"
    url_b = "https://example.com/path?a=1&b=2"
    url_c = "https://example.com/other"

    uuid_a = manager.generate_uuid(url_a)
    uuid_b = manager.generate_uuid(url_b)
    uuid_c = manager.generate_uuid(url_c)

    assert uuid_a == uuid_b
    assert uuid_a != uuid_c


def test_generate_uuid_ignores_default_ports(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache", size_limit_mb=1)

    http_with_port = "http://example.com:80/path"
    http_without_port = "http://example.com/path"
    https_with_port = "https://example.com:443/path"
    https_without_port = "https://example.com/path"

    assert manager.generate_uuid(http_with_port) == manager.generate_uuid(http_without_port)
    assert manager.generate_uuid(https_with_port) == manager.generate_uuid(https_without_port)


def test_set_and_get_roundtrip(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache", size_limit_mb=1)
    url = "https://example.com/artigo"
    payload = _build_analysis()

    assert manager.get("https://example.com/novo") is None

    stored = manager.set(url, payload)
    assert stored["enrichment"]["summary"] == "Resumo de teste"

    cached = manager.get(url)
    assert cached is not None
    assert cached["enrichment"]["relevance"] == EXPECTED_RELEVANCE_SCORE

    stats = manager.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1
    assert pytest.approx(stats["cache_hit_rate"], rel=1e-3) == EXPECTED_CACHE_HIT_RATE
    assert stats["total_entries"] == 1


def test_cleanup_removes_old_entries(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache", size_limit_mb=1)
    url = "https://example.com/desatualizado"
    manager.set(url, _build_analysis())

    uuid_value = manager.generate_uuid(url)
    entry = manager._cache.get(uuid_value)  # type: ignore[attr-defined]
    assert entry is not None
    entry["last_used"] = datetime.now(UTC) - timedelta(days=120)
    manager._cache.set(uuid_value, entry)  # type: ignore[attr-defined]

    removed = manager.cleanup_old_entries(90)
    assert removed == 1
    assert not manager.exists(url)


def test_missing_entry_counts_as_miss(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache", size_limit_mb=1)
    assert manager.get("https://example.com/absent") is None
    stats = manager.get_stats()
    assert stats["cache_hits"] == 0
    assert stats["cache_misses"] == 1
