"""Gemini embeddings integration for the RAG subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable, Sequence

try:  # pragma: no cover - optional dependency during testing
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - handled gracefully
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]


@dataclass(slots=True)
class EmbeddingConfig:
    """Configuration options for :class:`GeminiEmbedder`."""

    model: str = "gemini-embedding-001"
    output_dimensionality: int = 768
    batch_size: int = 100


class GeminiEmbedder:
    """Helper that proxies embedding requests to the Gemini API."""

    def __init__(self, config: EmbeddingConfig, client: Any) -> None:
        self.config = config
        self.client = client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embeddings for *texts* using the document task type."""

        return [self._embed_text(text, task_type="RETRIEVAL_DOCUMENT") for text in texts]

    def embed_query(self, query: str) -> list[float]:
        """Return an embedding for the supplied *query*."""

        return self._embed_text(query, task_type="RETRIEVAL_QUERY")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _embed_text(self, text: str, *, task_type: str) -> list[float]:
        """Call the Gemini API for a single text block."""

        if not text:
            return []

        response = self._call_embed_content(text, task_type=task_type)
        return self._extract_values(response)

    def _call_embed_content(self, text: str, *, task_type: str) -> Any:
        """Invoke ``models.embed_content`` with the appropriate arguments."""

        model = getattr(self.client, "models", self.client)
        embed_method = getattr(model, "embed_content")

        if types is not None:
            config = types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.config.output_dimensionality,
            )
            return embed_method(
                model=self.config.model,
                contents=text,
                config=config,
            )

        # Fall back to a simple namespace so tests can run without the SDK.
        config = SimpleNamespace(
            task_type=task_type,
            output_dimensionality=self.config.output_dimensionality,
        )
        return embed_method(
            model=self.config.model,
            contents=text,
            config=config,
        )

    @staticmethod
    def _extract_values(response: Any) -> list[float]:
        """Extract the embedding vector from the Gemini response."""

        if response is None:
            return []

        embedding_obj = getattr(response, "embedding", None)
        if embedding_obj is not None:
            values = getattr(embedding_obj, "values", None)
            if isinstance(values, Iterable):
                return [float(value) for value in values]

        embeddings = getattr(response, "embeddings", None)
        if embeddings:
            first = embeddings[0]
            values = getattr(first, "values", first)
            if isinstance(values, Iterable):
                return [float(value) for value in values]

        # Some client implementations may return mappings or dicts.
        if isinstance(response, dict):  # pragma: no cover - defensive
            values = response.get("embedding") or response.get("values")
            if isinstance(values, Iterable):
                return [float(value) for value in values]

        return []


__all__ = ["EmbeddingConfig", "GeminiEmbedder"]

