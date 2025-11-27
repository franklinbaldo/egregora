"""RAG backend protocol.

Defines the interface that all RAG backends must implement.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from egregora.data_primitives.document import Document
from egregora.rag.models import RAGQueryRequest, RAGQueryResponse


class RAGBackend(Protocol):
    """Interface for RAG backends.

    This protocol defines the contract that all RAG backend implementations
    must satisfy. Backends are responsible for:

    - Filtering documents to text-only content
    - Chunking documents into manageable pieces
    - Computing embeddings for chunks
    - Upserting chunks into the vector store
    - Executing vector similarity search

    Implementations:
        - DuckDBRAGBackend: Legacy DuckDB VSS implementation (deprecated)
        - LanceDBRAGBackend: New LanceDB implementation (recommended)

    """

    async def index_documents(self, docs: Sequence[Document]) -> None:
        """Index a batch of Documents into the RAG knowledge base (async).

        The implementation is responsible for:
        - Filtering to text documents (skipping bytes content)
        - Chunking per document according to backend strategy
        - Computing embeddings for all chunks (async)
        - Upserting into the vector store

        Args:
            docs: Sequence of Document instances to index

        Raises:
            ValueError: If documents are invalid or cannot be indexed
            RuntimeError: If embedding or storage operations fail

        """
        ...

    async def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        """Execute vector search in the knowledge base (async).

        Returns ranked hits pointing back to original documents.

        Args:
            request: Query parameters (text, top_k, filters)

        Returns:
            Response containing ranked RAGHit results

        Raises:
            ValueError: If query parameters are invalid
            RuntimeError: If search operation fails

        """
        ...


__all__ = ["RAGBackend"]
