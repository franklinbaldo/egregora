from __future__ import annotations

from egregora.cache import (
    build_embedding_namespace,
    create_embedding_cache,
    load_cached_embedding,
    store_cached_embedding,
)


def test_embedding_cache_hit(tmp_path):
    namespace = build_embedding_namespace(
        model="test-model",
        dimension=128,
        extra={"mode": "online"},
    )
    cache = create_embedding_cache(namespace, tmp_path)
    assert cache is not None

    payload = [0.1, 0.2, 0.3]
    store_cached_embedding(cache, namespace, "hello world", payload, kind="text")

    cached = load_cached_embedding(cache, namespace, "hello world", kind="text")
    assert cached == payload


def test_embedding_cache_miss_for_different_namespace(tmp_path):
    namespace_one = build_embedding_namespace(
        model="test-model",
        dimension=64,
        extra={"mode": "online"},
    )
    namespace_two = build_embedding_namespace(
        model="test-model",
        dimension=64,
        extra={"mode": "fallback"},
    )

    cache = create_embedding_cache(namespace_one, tmp_path)
    assert cache is not None

    store_cached_embedding(cache, namespace_one, "hello world", [1.0], kind="text")

    cached = load_cached_embedding(cache, namespace_two, "hello world", kind="text")
    assert cached is None
