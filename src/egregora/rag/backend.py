"""VectorStore protocol.

Defines the interface that all RAG backends must implement.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from egregora.data_primitives.document import Document
from egregora.rag.models import RAGQueryRequest, RAGQueryResponse


@runtime_checkable
class VectorStore(Protocol):
    """Interface for Vector Store backends.

    This protocol defines the contract that all RAG backend implementations
    must satisfy. Backends are responsible for storage and retrieval of
    embeddings.
    """

    @abstractmethod
    def add(self, documents: Sequence[Document]) -> int:
        """Add documents to the store.

        Args:
            documents: Sequence of Document instances to index

        Returns:
            Number of documents successfully indexed

        """
        ...

    @abstractmethod
    def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Execute vector search in the knowledge base.

        Args:
            request: Query parameters

        Returns:
            Response containing ranked results

        """
        ...

    @abstractmethod
    def delete(self, document_ids: list[str]) -> int:
        """Delete documents from the store.

        Args:
            document_ids: List of document IDs to delete

        Returns:
            Number of documents deleted

        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Count total documents in the store."""
        ...

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the store (index size, etc)."""
        ...


__all__ = ["VectorStore"]
