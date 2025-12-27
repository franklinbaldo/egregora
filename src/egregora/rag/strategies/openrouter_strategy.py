"""OpenRouter embedding strategy implementation.

Defensive implementation following sapper persona: fail fast, fail clearly.
"""

from __future__ import annotations

import os

from egregora.llm.providers.openrouter_embedding import (
    embed_with_openrouter,
    get_embedding_dimension,
)
from egregora.rag.strategies import EmbeddingStrategy, TaskType
from egregora.rag.strategies.exceptions import ProviderNotAvailableError


class OpenRouterEmbeddingStrategy(EmbeddingStrategy):
    """Embedding strategy for OpenRouter provider.

    Defensive guarantees:
    - Fails fast if API key is missing (is_available check)
    - Validates model format at construction
    - Raises specific exceptions for each failure mode
    """

    def __init__(self, model: str) -> None:
        """Initialize OpenRouter strategy.

        Args:
            model: OpenRouter model identifier (e.g., "qwen/qwen3-embedding-0.6b")

        """
        self.model = model
        self._dimension = get_embedding_dimension(model)

    def get_dimension(self) -> int:
        """Get the vector dimension for this model.

        Returns:
            Vector dimension (e.g., 512 for qwen/qwen3-embedding-0.6b)

        """
        return self._dimension

    def embed(
        self,
        texts: list[str],
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Generate embeddings using OpenRouter.

        Args:
            texts: List of strings to embed
            task_type: Type of embedding task (ignored by OpenRouter)

        Returns:
            List of embedding vectors

        Raises:
            ProviderNotAvailableError: If API key is not set

        """
        # Defensive: fail fast if provider not available
        if not self.is_available():
            raise ProviderNotAvailableError(
                "OpenRouter",
                "API key not set (OPENROUTER_API_KEY environment variable required)",
            )

        # Delegate to OpenRouter embedding function
        return embed_with_openrouter(texts, model=self.model, task_type=task_type)

    def is_available(self) -> bool:
        """Check if OpenRouter provider is available.

        Returns:
            True if OPENROUTER_API_KEY is set

        """
        return os.environ.get("OPENROUTER_API_KEY") is not None
