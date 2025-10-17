"""Embedding helpers built on top of ChromaDB."""

from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import logging

from chromadb.utils import embedding_functions
from diskcache import Cache


class _FallbackEmbedding:
    """Deterministic, offline-friendly embedding used when Gemini is unavailable."""

    def __init__(self, dimension: int = 256, *, ngram_range: tuple[int, int] = (3, 5)) -> None:
        self._dimension = max(32, dimension)
        self._ngram_min = max(1, ngram_range[0])
        self._ngram_max = max(self._ngram_min, ngram_range[1])

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._vectorise(text) for text in input]

    def _vectorise(self, text: str) -> list[float]:
        features = self._extract_features(text)
        if not features:
            return [0.0] * self._dimension

        vector = [0.0] * self._dimension
        for feature, weight in features.items():
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=16).digest()
            position = int.from_bytes(digest[:4], "little") % self._dimension
            magnitude = int.from_bytes(digest[4:8], "little") / 0xFFFFFFFF
            vector[position] += float(weight) * (0.5 + 0.5 * magnitude)

        norm = sum(value * value for value in vector) ** 0.5
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def _extract_features(self, text: str) -> Counter[str]:
        lowered = text.lower()
        tokens = re.findall(r"[a-z0-9áéíóúàâêôãõç']+", lowered)
        if not tokens:
            return Counter()

        features: Counter[str] = Counter(tokens)
        features[lowered] += 1

        for first, second in zip(tokens, tokens[1:]):
            features[f"{first} {second}"] += 1

        for token in tokens:
            padded = f"^{token}$"
            length = len(padded)
            for size in range(self._ngram_min, min(self._ngram_max, length) + 1):
                for index in range(length - size + 1):
                    features[padded[index : index + size]] += 1

        return features


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
        if not isinstance(vector, list) or len(vector) != self._dimension:
            return None
        try:
            return [float(value) for value in vector]
        except (TypeError, ValueError):
            return None

    def _store_cache(self, text: str, values: Iterable[float]) -> None:
        if self._cache is None:
            return
        vector = [float(value) for value in values]
        record = {
            "vector": vector,
            "namespace": self._cache_namespace,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        try:
            self._cache.set(self._cache_key(text), record)
        except Exception:  # diskcache is permissive; ensure failures do not break inference
            logging.getLogger(__name__).debug("Failed to cache embedding", exc_info=True)

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Embed a list of texts."""

        if not input:
            return []

        results: list[list[float] | None] = [None] * len(input)
        pending: list[tuple[int, str]] = []

        for index, text in enumerate(input):
            cached = self._lookup_cache(text)
            if cached is not None:
                results[index] = cached
            else:
                pending.append((index, text))

        if pending:
            embeddings = self._embed_model([text for _, text in pending])
            for (position, text), embedding in zip(pending, embeddings, strict=False):
                vector = [float(value) for value in embedding]
                self._store_cache(text, vector)
                results[position] = vector

        return [
            entry if entry is not None else [0.0] * self._dimension for entry in results
        ]

    @staticmethod
    def _build_cache_namespace(*, model_name: str, dimension: int, using_fallback: bool) -> str:
        mode = "fallback" if using_fallback else "online"
        return f"model={model_name}|dimension={dimension}|mode={mode}"


__all__ = ["CachedGeminiEmbedding"]
