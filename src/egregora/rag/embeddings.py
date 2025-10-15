"""Embedding helpers built on top of ChromaDB."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from chromadb.utils import embedding_functions
from diskcache import Cache


class _FallbackEmbedding:
    """Deterministic, offline-friendly embedding used when Gemini is unavailable."""

    def __init__(self, dimension: int = 256) -> None:
        self._dimension = max(32, dimension)

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

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._vectorise(text) for text in input]


class CachedGeminiEmbedding:
    """Gemini embeddings with optional disk caching and offline fallback."""

    def __init__(
        self,
        *,
        model_name: str,
        dimension: int,
        cache_dir: Path | None = None,
        api_key: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._api_key = api_key or os.getenv("GOOGLE_API_KEY")

        using_fallback = not self._api_key
        self._using_fallback = using_fallback

        cache_namespace = self._build_cache_namespace(
            model_name=model_name,
            dimension=dimension,
            using_fallback=using_fallback,
        )
        self._cache_namespace = cache_namespace

        cache: Cache | None = None
        if cache_dir:
            resolved_dir = Path(cache_dir).expanduser()
            resolved_dir.mkdir(parents=True, exist_ok=True)
            cache = Cache(directory=str(resolved_dir))
        self._cache = cache

        if not using_fallback:
            self._embed_model = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
                api_key=self._api_key, model_name=self._model_name
            )
        else:
            self._embed_model = _FallbackEmbedding(dimension)

    def _cache_key(self, text: str) -> str:
        base = f"{self._cache_namespace}|{text}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _lookup_cache(self, text: str) -> list[float] | None:
        if self._cache is None:
            return None
        record = self._cache.get(self._cache_key(text))
        if not isinstance(record, dict):
            return None
        if record.get("namespace") != self._cache_namespace:
            return None
        vector = record.get("vector")
        if not isinstance(vector, list):
            return None
        return [float(value) for value in vector]

    def _store_cache(self, text: str, values: Iterable[float]) -> None:
        if self._cache is None:
            return
        vector = [float(value) for value in values]
        record = {
            "vector": vector,
            "namespace": self._cache_namespace,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        self._cache.set(self._cache_key(text), record)

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Embed a list of texts."""
        results: list[list[float]] = []
        texts_to_embed: list[str] = []
        indices_to_embed: list[int] = []

        # First, check cache for existing embeddings
        for i, text in enumerate(input):
            cached = self._lookup_cache(text)
            if cached is not None:
                results.insert(i, cached)
            else:
                results.append([])  # placeholder
                texts_to_embed.append(text)
                indices_to_embed.append(i)

        if not texts_to_embed:
            return results

        # Embed the texts that were not in the cache
        embeddings = self._embed_model(texts_to_embed)

        # Store new embeddings in cache and fill in the results
        for i, embedding in enumerate(embeddings):
            original_index = indices_to_embed[i]
            text = texts_to_embed[i]
            self._store_cache(text, embedding)
            results[original_index] = embedding

        return results

    @staticmethod
    def _build_cache_namespace(*, model_name: str, dimension: int, using_fallback: bool) -> str:
        mode = "fallback" if using_fallback else "online"
        return f"model={model_name}|dimension={dimension}|mode={mode}"


__all__ = ["CachedGeminiEmbedding"]
