"""RAG (Retrieval Augmented Generation) module.

This module provides a high-level API for indexing and retrieving documents
using vector embeddings. It abstracts the underlying storage and embedding
implementation details.

Key Components:
- index_documents: Index a list of documents
- search: Search for relevant documents using a query string
- backend: The configured RAG backend (DuckDB or LanceDB)

Usage:
    >>> from egregora.rag import index_documents, search
    >>> index_documents([doc1, doc2])
    >>> results = search("what is the meaning of life?", top_k=5)
"""

import logging
from contextlib import suppress
from functools import lru_cache
from typing import TYPE_CHECKING

from egregora.config.settings import RAGSettings
from egregora.rag.backend import VectorStore
from egregora.rag.embedding_router import EmbeddingRouter, TaskType, get_embedding_router
from egregora.rag.lancedb_backend import LanceDBRAGBackend
from egregora.rag.models import RAGQueryRequest, RAGQueryResponse

if TYPE_CHECKING:
    from egregora_v3.core.types import Document


logger = logging.getLogger(__name__)


# Global backend instance (lazily initialized)
_backend: VectorStore | None = None


def get_backend() -> VectorStore:
    """Get or initialize the global RAG backend."""
    global _backend
    if _backend is None:
        from pathlib import Path
        from egregora.config import load_egregora_config

        try:
            config = load_egregora_config()
            lancedb_path = Path(config.paths.lancedb_dir)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load RAG config, using defaults")
            # Default fallback matching PathsSettings
            lancedb_path = Path(".egregora/lancedb")

        # Initialize LanceDB backend with embedding function
        # Note: We inject embed_fn here to decouple backend from router
        _backend = LanceDBRAGBackend(
            db_dir=lancedb_path,
            table_name="vectors",
            embed_fn=embed_fn,
        )
    return _backend


def reset_backend() -> None:
    """Reset the global backend instance (for testing/re-init)."""
    global _backend
    _backend = None


def index_documents(documents: list["Document"]) -> int:
    """Index a list of documents into the vector store.

    Args:
        documents: List of Document objects to index

    Returns:
        Number of documents successfully indexed
    """
    if not documents:
        return 0

    backend = get_backend()
    return backend.add(documents)


def search(request: RAGQueryRequest) -> RAGQueryResponse:
    """Search for documents similar to the query.

    Args:
        request: Search request object

    Returns:
        Search result object containing hits
    """
    backend = get_backend()
    return backend.query(request)


# Re-export embedding function helper for convenience
@lru_cache(maxsize=1)
def embed_fn(
    texts: tuple[str],
    task_type: TaskType = "RETRIEVAL_DOCUMENT",
    model: str | None = None,
) -> list[list[float]]:
    """Generate embeddings for a list of texts using the configured router.

    Args:
        texts: Tuple of strings to embed (tuple for lru_cache)
        task_type: Type of task (retrieval_query, retrieval_document, etc.)
        model: Optional model override

    Returns:
        List of embedding vectors
    """
    router = get_embedding_router()
    return router.embed(list(texts), task_type=task_type)
