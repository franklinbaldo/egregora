"""Embedding helpers built on top of LlamaIndex."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from diskcache import Cache
from llama_index.core.embeddings import BaseEmbedding

try:  # pragma: no cover - optional dependency
    from llama_index.embeddings.gemini import GeminiEmbedding
except ModuleNotFoundError:  # pragma: no cover - handled in fallback
    GeminiEmbedding = None  # type: ignore[misc]


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

    def _get_text_embedding(
        self, text: str
    ) -> list[float]:  # pragma: no cover - delegated to sync path
        return self._vectorise(text)

    def _get_query_embedding(
        self, query: str
    ) -> list[float]:  # pragma: no cover - delegated to sync path
        return self._vectorise(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:  # pragma: no cover - delegated
        return self._vectorise(text)

    async def _aget_query_embedding(
        self, query: str
    ) -> list[float]:  # pragma: no cover - delegated
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

        cache_namespace = self._build_cache_namespace(
            model_name=model_name,
            dimension=dimension,
            using_fallback=using_fallback,
        )
        object.__setattr__(self, "_cache_namespace", cache_namespace)

        cache: Cache | None = None
        if cache_dir:
            resolved_dir = Path(cache_dir).expanduser()
            resolved_dir.mkdir(parents=True, exist_ok=True)
            cache = Cache(directory=str(resolved_dir))
        object.__setattr__(self, "_cache", cache)

        if not using_fallback and GeminiEmbedding is not None:
            embed_model: BaseEmbedding = GeminiEmbedding(
                model_name=model_name,
                api_key=resolved_api_key,
            )
        else:
            embed_model = _FallbackEmbedding(dimension)
        object.__setattr__(self, "_embed_model", embed_model)

    def _cache_key(self, text: str, *, kind: str) -> str:
        base = f"{self._cache_namespace}|{kind}|{text}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _lookup_cache(self, text: str, *, kind: str) -> list[float] | None:
        cache = self._cache
        if cache is None:
            return None
        record = cache.get(self._cache_key(text, kind=kind))
        if not isinstance(record, dict):
            return None
        if record.get("namespace") != self._cache_namespace:
            return None
        vector = record.get("vector")
        if not isinstance(vector, list):
            return None
        return [float(value) for value in vector]

    def _store_cache(self, text: str, values: Iterable[float], *, kind: str) -> None:
        cache = self._cache
        if cache is None:
            return
        vector = [float(value) for value in values]
        record = {
            "vector": vector,
            "namespace": self._cache_namespace,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        cache.set(self._cache_key(text, kind=kind), record)

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

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed(text, kind="text")

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed(query, kind="query")

    async def _aget_text_embedding(
        self, text: str
    ) -> list[float]:  # pragma: no cover - simple passthrough
        return self._get_text_embedding(text)

    async def _aget_query_embedding(
        self, query: str
    ) -> list[float]:  # pragma: no cover - simple passthrough
        return self._get_query_embedding(query)

    @staticmethod
    def _build_cache_namespace(*, model_name: str, dimension: int, using_fallback: bool) -> str:
        mode = "fallback" if using_fallback else "online"
        return f"model={model_name}|dimension={dimension}|mode={mode}"


__all__ = ["CachedGeminiEmbedding"]
