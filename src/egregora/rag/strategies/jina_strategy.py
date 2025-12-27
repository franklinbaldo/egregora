"""Jina AI embedding strategy implementation.

Defensive implementation following sapper persona: fail fast, fail clearly.
"""

from __future__ import annotations

import os

from egregora.llm.providers.jina_embedding import (
    embed_with_jina,
    get_embedding_dimension,
)
from egregora.rag.strategies import EmbeddingStrategy, TaskType
from egregora.rag.strategies.exceptions import ProviderNotAvailableError


class JinaEmbeddingStrategy(EmbeddingStrategy):
    """Embedding strategy for Jina AI provider.

    Defensive guarantees:
    - Fails fast if API key is missing (is_available check)
    - Validates model format at construction
    - Raises specific exceptions for each failure mode

    Supported Models:
    - jina-embeddings-v3: 1024 dimensions
    - jina-embeddings-v4: 2048 dimensions
    """

    def __init__(self, model: str) -> None:
        """Initialize Jina strategy.

        Args:
            model: Jina model identifier (e.g., "jina-embeddings-v3")

        """
        self.model = model
        self._dimension = get_embedding_dimension(model)

    def get_dimension(self) -> int:
        """Get the vector dimension for this model.

        Returns:
            Vector dimension (1024 for v3, 2048 for v4)

        """
        return self._dimension

    def embed(
        self,
        texts: list[str],
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Generate embeddings using Jina AI.

        Args:
            texts: List of strings to embed
            task_type: Type of embedding task (mapped to Jina task parameter)

        Returns:
            List of embedding vectors

        Raises:
            ProviderNotAvailableError: If API key is not set

        """
        # Defensive: fail fast if provider not available
        if not self.is_available():
            raise ProviderNotAvailableError(
                "Jina AI",
                "API key not set (JINA_API_KEY environment variable required)",
            )

        # Map our task types to Jina's task parameter
        task_mapping = {
            "RETRIEVAL_QUERY": "retrieval.query",
            "RETRIEVAL_DOCUMENT": "retrieval.passage",
            "SEMANTIC_SIMILARITY": "text-matching",
        }
        jina_task = task_mapping.get(task_type)

        # Delegate to Jina embedding function
        return embed_with_jina(texts, model=self.model, task=jina_task, normalized=True)

    def is_available(self) -> bool:
        """Check if Jina AI provider is available.

        Returns:
            True if JINA_API_KEY is set

        """
        return os.environ.get("JINA_API_KEY") is not None
