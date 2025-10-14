"""Gemini embedding helpers for the refactored pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import polars as pl

Vector = list[float]


@dataclass(slots=True)
class EmbeddingResult:
    """Container used by the CLI to expose embedding metadata."""

    total_texts: int
    model: str
    vector_column: str
    text_column: str


class GeminiEmbedder:
    """Thin wrapper around the Gemini embeddings API with dataframe helpers."""

    def __init__(
        self,
        *,
        model: str = "models/embedding-001",
        batch_size: int = 10,
        max_input_chars: int = 2048,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.batch_size = max(int(batch_size), 1)
        self.max_input_chars = max(int(max_input_chars), 1)
        self._client = client
        self._models_accessor: Any | None = None
        self._api_key = api_key

        if client is not None:
            self._models_accessor = getattr(client, "models", client)
        else:
            self._client = self._build_client()
            self._models_accessor = getattr(self._client, "models", self._client)

    def embed_text(self, text: str | None) -> Vector:
        """Return a single embedding for ``text`` using chunk averaging."""

        if text is None:
            return []

        normalised = text.strip()
        if not normalised:
            return []

        chunks = self._chunk_text(normalised)
        vectors = [self._embed_chunk(chunk) for chunk in chunks]
        return self._average_vectors(vectors)

    def embed_messages(self, texts: Iterable[str | None]) -> list[Vector]:
        """Embed an iterable of texts preserving order."""

        results: list[Vector] = []
        batch: list[str | None] = []
        for text in texts:
            batch.append(text)
            if len(batch) >= self.batch_size:
                results.extend(self._embed_batch(batch))
                batch.clear()
        if batch:
            results.extend(self._embed_batch(batch))
        return results

    def embed_dataframe(
        self,
        frame: pl.DataFrame,
        *,
        text_column: str = "message",
        vector_column: str = "vector",
    ) -> pl.DataFrame:
        """Return ``frame`` with ``vector_column`` populated with embeddings."""

        if text_column not in frame.columns:
            raise KeyError(f"Coluna '{text_column}' não encontrada no DataFrame para embedding")

        vectors = self.embed_messages(frame.get_column(text_column))
        series = pl.Series(vector_column, vectors, dtype=pl.List(pl.Float64))
        return frame.with_columns(series)

    # ------------------------------------------------------------------
    # Internal helpers
    def _build_client(self) -> Any:
        try:  # pragma: no cover - import guarded for optional dependency
            from google import genai  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "A dependência opcional 'google-genai' não está instalada. "
                "Instale-a para gerar embeddings com Gemini."
            ) from exc

        api_key = (
            self._api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if not api_key:  # pragma: no cover - runtime guard
            raise RuntimeError("Defina GEMINI_API_KEY ou GOOGLE_API_KEY para usar embeddings do Gemini.")

        return genai.Client(api_key=api_key)

    def _embed_batch(self, texts: Sequence[str | None]) -> list[Vector]:
        return [self.embed_text(text) for text in texts]

    def _embed_chunk(self, text: str) -> Vector:
        response = self._models_accessor.embed_content(model=self.model, content=text)
        embedding = getattr(response, "embedding", None)
        if embedding is None:
            embedding = response.get("embedding")  # type: ignore[assignment]
        if embedding is None:
            raise RuntimeError("A resposta do Gemini não contém o vetor de embedding esperado.")
        return [float(value) for value in embedding]

    def _chunk_text(self, text: str) -> list[str]:
        if len(text) <= self.max_input_chars:
            return [text]
        return [
            text[index : index + self.max_input_chars]
            for index in range(0, len(text), self.max_input_chars)
        ]

    @staticmethod
    def _average_vectors(vectors: Sequence[Vector]) -> Vector:
        filtered = [vector for vector in vectors if vector]
        if not filtered:
            return []
        length = len(filtered[0])
        totals = [0.0] * length
        for vector in filtered:
            if len(vector) != length:
                raise ValueError("Todos os vetores devem ter o mesmo comprimento para média.")
            for index, value in enumerate(vector):
                totals[index] += value
        count = float(len(filtered))
        return [value / count for value in totals]


__all__ = ["EmbeddingResult", "GeminiEmbedder"]
