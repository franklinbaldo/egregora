"""Strategy pattern for RAG embedding providers.

This module defines a clean abstraction for embedding providers, following the
strategy pattern to decouple provider-specific logic from the RAG system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

TaskType = Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT", "SEMANTIC_SIMILARITY", "CLASSIFICATION", "CLUSTERING"]


class EmbeddingStrategy(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the vector dimension for this provider's model."""
        ...

    @abstractmethod
    def embed(
        self,
        texts: list[str],
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of strings to embed
            task_type: Type of embedding task

        Returns:
            List of embedding vectors
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available (API key set, etc.)."""
        ...


class EmbeddingProviderFactory:
    """Factory for creating embedding strategy instances based on model name."""

    @staticmethod
    def create(model: str) -> EmbeddingStrategy:
        """Create an embedding strategy for the given model.

        Args:
            model: Model identifier (e.g., "models/gemini-embedding-001" or "qwen/qwen3-embedding-0.6b")

        Returns:
            Appropriate EmbeddingStrategy instance

        Raises:
            ValueError: If model format is not recognized
        """
        from egregora.llm.providers.openrouter_embedding import is_openrouter_embedding_model

        if is_openrouter_embedding_model(model):
            from egregora.rag.strategies.openrouter_strategy import OpenRouterEmbeddingStrategy
            return OpenRouterEmbeddingStrategy(model)
        elif model.startswith("models/"):
            from egregora.rag.strategies.gemini_strategy import GeminiEmbeddingStrategy
            return GeminiEmbeddingStrategy(model)
        else:
            msg = f"Unsupported embedding model format: {model}"
            raise ValueError(msg)


__all__ = [
    "EmbeddingStrategy",
    "EmbeddingProviderFactory",
    "TaskType",
]
