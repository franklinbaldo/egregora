"""Embedding helpers built on top of LlamaIndex."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, List

from llama_index.core.embeddings import BaseEmbedding

try:  # pragma: no cover - optional dependency
    from llama_index.embeddings.gemini import GeminiEmbedding
except ModuleNotFoundError:  # pragma: no cover - handled in fallback
    GeminiEmbedding = None  # type: ignore[misc]

from egregora.cache import (
    build_embedding_namespace,
    create_embedding_cache,
    load_cached_embedding,
    store_cached_embedding,
)


class _FallbackEmbedding(BaseEmbedding):
    """Deterministic, offline-friendly embedding used when Gemini is unavailable."""

    def __init__(self, dimension: int = 256) -> None:
        super().__init__()
        object.__setattr__(self, "_dimension", max(32, dimension))

    def _vectorise(self, text: str) -> list[float]:
        if not text:
            return [0.0] * self._dimension

        vector = [0.0] * self._dimension
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(0, len(digest), 2):
                position = digest[index] % self._dimension
                increment = digest[index + 1] / 255.0
                vector[position] += increment

        norm = sum(value * value for value in vector) ** 0.5
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _get_text_embedding(self, text: str) -> List[float]:  # pragma: no cover - delegated to sync path
        return self._vectorise(text)

    def _get_query_embedding(self, query: str) -> List[float]:  # pragma: no cover - delegated to sync path
        return self._vectorise(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:  # pragma: no cover - delegated
        return self._vectorise(text)

    async def _aget_query_embedding(self, query: str) -> List[float]:  # pragma: no cover - delegated
        return self._vectorise(query)


class CachedGeminiEmbedding(BaseEmbedding):
    """Gemini embeddings with optional disk caching and offline fallback."""

    def __init__(
        self,
        *,
        model_name: str,
        dimension: int,
        cache_dir: Path | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__()
        object.__setattr__(self, "_model_name", model_name)
        object.__setattr__(self, "_dimension", dimension)
        resolved_api_key = api_key or os.getenv("GOOGLE_API_KEY")
        object.__setattr__(self, "_api_key", resolved_api_key)

        using_fallback = not resolved_api_key or GeminiEmbedding is None
        object.__setattr__(self, "_using_fallback", using_fallback)

        cache_namespace = build_embedding_namespace(
            model=model_name,
            dimension=dimension,
            extra={"mode": "fallback" if using_fallback else "online"},
        )
        cache = create_embedding_cache(cache_namespace, cache_dir)
        object.__setattr__(self, "_cache", cache)
        object.__setattr__(self, "_cache_namespace", cache_namespace)

        if not using_fallback and GeminiEmbedding is not None:
            embed_model: BaseEmbedding = GeminiEmbedding(
                model_name=model_name,
                api_key=resolved_api_key,
            )
        else:
            embed_model = _FallbackEmbedding(dimension)
        object.__setattr__(self, "_embed_model", embed_model)

    def _lookup_cache(self, text: str, *, kind: str) -> list[float] | None:
        cache = self._cache
        if not cache:
            return None
        return load_cached_embedding(cache, self._cache_namespace, text, kind=kind)

    def _store_cache(self, text: str, values: Iterable[float], *, kind: str) -> None:
        cache = self._cache
        if not cache:
            return
        store_cached_embedding(cache, self._cache_namespace, text, values, kind=kind)

    def _embed(self, text: str, *, kind: str) -> list[float]:
        cached = self._lookup_cache(text, kind=kind)
        if cached is not None:
            return cached

        if kind == "query":
            vector = self._embed_model.get_query_embedding(text)  # type: ignore[attr-defined]
        else:
            vector = self._embed_model.get_text_embedding(text)  # type: ignore[attr-defined]

        self._store_cache(text, vector, kind=kind)
        return vector

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed(text, kind="text")

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed(query, kind="query")

    async def _aget_text_embedding(self, text: str) -> List[float]:  # pragma: no cover - simple passthrough
        return self._get_text_embedding(text)

    async def _aget_query_embedding(self, query: str) -> List[float]:  # pragma: no cover - simple passthrough
        return self._get_query_embedding(query)


__all__ = ["CachedGeminiEmbedding"]

