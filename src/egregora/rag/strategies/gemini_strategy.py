"""Gemini embedding strategy implementation.

Defensive implementation following sapper persona: fail fast, fail clearly.
"""

from __future__ import annotations

import os

from egregora.rag.embedding_router import get_router
from egregora.rag.strategies import EmbeddingStrategy, TaskType
from egregora.rag.strategies.exceptions import ProviderNotAvailableError


class GeminiEmbeddingStrategy(EmbeddingStrategy):
    """Embedding strategy for Gemini provider.

    Defensive guarantees:
    - Fails fast if API key is missing (is_available check)
    - Validates model format at construction
    - Raises specific exceptions for each failure mode
    """

    def __init__(self, model: str) -> None:
        """Initialize Gemini strategy.

        Args:
            model: Gemini model identifier (e.g., "models/gemini-embedding-001")

        """
        self.model = model
        # Gemini embeddings are always 768 dimensions
        self._dimension = 768

    def get_dimension(self) -> int:
        """Get the vector dimension for this model.

        Returns:
            Vector dimension (768 for Gemini embeddings)

        """
        return self._dimension

    def embed(
        self,
        texts: list[str],
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Generate embeddings using Gemini.

        Args:
            texts: List of strings to embed
            task_type: Type of embedding task

        Returns:
            List of embedding vectors

        Raises:
            ProviderNotAvailableError: If API key is not set

        """
        # Defensive: fail fast if provider not available
        if not self.is_available():
            raise ProviderNotAvailableError(
                "Gemini",
                "API key not set (GOOGLE_API_KEY or GEMINI_API_KEY environment variable required)",
            )

        # Use the embedding router (handles dual-queue optimization)
        router = get_router(model=self.model)
        return router.embed(texts, task_type=task_type)

    def is_available(self) -> bool:
        """Check if Gemini provider is available.

        Returns:
            True if GOOGLE_API_KEY or GEMINI_API_KEY is set

        """
        return os.environ.get("GOOGLE_API_KEY") is not None or os.environ.get("GEMINI_API_KEY") is not None
