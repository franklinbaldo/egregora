from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.cache_manager import CacheManager


def _build_analysis(model: str = "gemini-test") -> dict[str, object]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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


def test_generate_uuid_normalizes_urls(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache")
    url_a = "https://Example.com/path/?b=2&a=1"
    url_b = "https://example.com/path?a=1&b=2"
    url_c = "https://example.com/other"

    uuid_a = manager.generate_uuid(url_a)
    uuid_b = manager.generate_uuid(url_b)
    uuid_c = manager.generate_uuid(url_c)

    assert uuid_a == uuid_b
    assert uuid_a != uuid_c


def test_set_and_get_roundtrip(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache")
    url = "https://example.com/artigo"
    payload = _build_analysis()

    assert manager.get("https://example.com/novo") is None

    stored = manager.set(url, payload)
    assert stored["enrichment"]["summary"] == "Resumo de teste"

    cached = manager.get(url)
    assert cached is not None
    assert cached["enrichment"]["relevance"] == 4

    stats = manager.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1
    assert pytest.approx(stats["cache_hit_rate"], rel=1e-3) == 0.5

    index_path = manager.index_path
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    entry = next(iter(index_data["entries"].values()))
    assert entry["hit_count"] == 1
    assert entry["analysis_path"].startswith("cache/analyses/")


def test_cleanup_removes_old_entries(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache")
    url = "https://example.com/desatualizado"
    manager.set(url, _build_analysis())

    uuid_value = manager.generate_uuid(url)
    manager._index["entries"][uuid_value]["last_used"] = (
        datetime.now(timezone.utc) - timedelta(days=120)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    manager._save_index()

    removed = manager.cleanup_old_entries(90)
    assert removed == 1
    assert not manager.exists(url)


def test_corrupted_analysis_marks_entry_as_error(tmp_path: Path) -> None:
    manager = CacheManager(tmp_path / "cache")
    url = "https://example.com/corrompido"
    manager.set(url, _build_analysis())

    uuid_value = manager.generate_uuid(url)
    entry = manager._index["entries"][uuid_value]
    analysis_path = manager._resolve_analysis_path(entry["analysis_path"])
    assert analysis_path is not None
    analysis_path.write_text("{invalid}", encoding="utf-8")

    cached = manager.get(url)
    assert cached is None
    updated_entry = manager._index["entries"][uuid_value]
    assert updated_entry["status"] == "error"
