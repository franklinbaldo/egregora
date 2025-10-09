"""Tests for embedding cache helpers and wrappers."""

from __future__ import annotations

from pathlib import Path

import pytest

from egregora.cache import build_namespace, create_cache, load_vector, store_vector
from egregora.rag.embedding_cache import EmbeddingCache
from egregora.rag.embeddings import CachedGeminiEmbedding


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "cache"
    directory.mkdir()
    return directory


def test_build_namespace_sorts_extra() -> None:
    namespace = build_namespace(model="gemini", dimension=256, extra={"mode": "online", "tenant": "alpha"})
    assert namespace == "model=gemini|dimension=256|mode=online|tenant=alpha"


def test_low_level_helpers_round_trip(cache_dir: Path) -> None:
    cache = create_cache(cache_dir)
    namespace = build_namespace(model="test", dimension=4)
    text = "hello world"

    assert load_vector(cache, namespace, text) is None

    metadata = store_vector(cache, namespace, text, [1, 2, 3, 4])
    assert metadata is not None
    assert metadata.dimension == 4

    stored = load_vector(cache, namespace, text)
    assert stored == [1.0, 2.0, 3.0, 4.0]


def test_embedding_cache_wrapper(cache_dir: Path) -> None:
    cache = EmbeddingCache(cache_dir, model="gemini", dimension=8)
    assert cache.get("text") is None
    cache.set("text", [0.1] * 8)
    assert cache.get("text") == [pytest.approx(0.1)] * 8


def test_cached_gemini_embedding_hits_cache(monkeypatch: pytest.MonkeyPatch, cache_dir: Path) -> None:
    calls: list[str] = []

    class StubEmbedding:
        def get_text_embedding(self, text: str) -> list[float]:
            calls.append(text)
            return [1.0, 0.0]

        def get_query_embedding(self, text: str) -> list[float]:
            calls.append(f"query:{text}")
            return [0.5, 0.5]

    embedding = CachedGeminiEmbedding(
        model_name="models/gemini-test",
        dimension=2,
        cache_dir=cache_dir,
        api_key=None,
    )
    # Override fallback model with stub to count calls.
    object.__setattr__(embedding, "_embed_model", StubEmbedding())

    first = embedding._get_text_embedding("hello")
    second = embedding._get_text_embedding("hello")
    assert first == [1.0, 0.0]
    assert second == [1.0, 0.0]
    assert calls == ["hello"]

    query_first = embedding._get_query_embedding("what")
    query_second = embedding._get_query_embedding("what")
    assert query_first == [0.5, 0.5]
    assert query_second == [0.5, 0.5]
    assert calls == ["hello", "query:what"]
