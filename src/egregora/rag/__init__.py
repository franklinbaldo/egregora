r"""RAG (Retrieval-Augmented Generation) package for Egregora.

This package provides a simple RAG implementation using LanceDB for vector storage,
with DuckDB integration for SQL-based analytics and filtering.

Public API:
    - get_backend(): Get the configured LanceDB RAG backend
    - index_documents(): Index documents into RAG
    - search(): Execute vector similarity search
    - RAGHit, RAGQueryRequest, RAGQueryResponse: Core data models

DuckDB Integration:
    - search_to_table(): Convert RAG results to Ibis/DuckDB table
    - join_with_messages(): Join RAG results with message data
    - search_with_filters(): Vector search with SQL filtering

Configuration:
    Set paths in .egregora/config.yml:
    ```yaml
    paths:
      lancedb_dir: .egregora/lancedb

    rag:
      top_k: 5
    ```

Example:
    >>> from egregora.rag import index_documents, search, RAGQueryRequest
    >>> from egregora.data_primitives import Document, DocumentType
    >>>
    >>> # Index documents
    >>> doc = Document(content="# Post\n\nContent", type=DocumentType.POST)
    >>> index_documents([doc])
    >>>
    >>> # Search
    >>> request = RAGQueryRequest(text="search query", top_k=5)
    >>> response = search(request)
    >>> for hit in response.hits:
    ...     print(f"{hit.score:.2f}: {hit.text[:50]}")
    >>>
    >>> # DuckDB integration - query results as SQL table
    >>> from egregora.rag.duckdb_integration import search_to_table
    >>> table = search_to_table(RAGQueryRequest(text="query", top_k=10))
    >>> high_scores = table.filter(table.score > 0.8)
    >>> print(high_scores.execute())

"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from egregora.config.settings import EgregoraConfig, load_egregora_config
from egregora.data_primitives.document import Document, DocumentType
from egregora.rag.backend import RAGBackend
from egregora.rag.embeddings import embed_texts_in_batch
from egregora.rag.lancedb_backend import LanceDBRAGBackend
from egregora.rag.models import RAGHit, RAGQueryRequest, RAGQueryResponse

logger = logging.getLogger(__name__)

# Global backend instance (lazy-initialized)
_backend: RAGBackend | None = None


def _create_backend() -> RAGBackend:
    """Create LanceDB RAG backend based on configuration.

    Returns:
        LanceDBRAGBackend instance

    Raises:
        RuntimeError: If backend initialization fails

    """
    # Try to load config from current directory
    try:
        config = load_egregora_config(Path.cwd())
    except (OSError, ValueError):
        logger.exception(
            "Failed to load .egregora/config.yml - using default configuration. "
            "Your custom settings will be ignored."
        )
        # Fall back to default config
        config = EgregoraConfig()

    # Determine lancedb_dir from config
    lancedb_dir = Path.cwd() / ".egregora" / "lancedb"
    if hasattr(config, "paths") and hasattr(config.paths, "lancedb_dir"):
        lancedb_dir = Path.cwd() / config.paths.lancedb_dir

    # Get embedding model
    embedding_model = config.models.embedding

    # Convert indexable_types from string list to DocumentType set
    indexable_types: set[DocumentType] | None = None
    if hasattr(config.rag, "indexable_types") and config.rag.indexable_types:
        indexable_types = set()
        for type_str in config.rag.indexable_types:
            try:
                doc_type = DocumentType[type_str.upper()]
                indexable_types.add(doc_type)
            except KeyError:
                logger.warning("Unknown document type in config: %s (skipping)", type_str)

    # Create embedding function that wraps the existing embedder
    def embed_fn(texts: Sequence[str]) -> list[list[float]]:
        return embed_texts_in_batch(list(texts), model=embedding_model)

    logger.info("Creating LanceDB RAG backend at %s", lancedb_dir)
    return LanceDBRAGBackend(
        db_dir=lancedb_dir,
        table_name="rag_embeddings",
        embed_fn=embed_fn,
        top_k_default=config.rag.top_k,
        indexable_types=indexable_types,
    )


def get_backend() -> RAGBackend:
    """Get the configured RAG backend.

    Lazily initializes the LanceDB backend on first call.

    Returns:
        RAGBackend instance (LanceDB implementation)

    Raises:
        RuntimeError: If backend initialization fails

    """
    global _backend  # noqa: PLW0603
    if _backend is None:
        _backend = _create_backend()
    return _backend


def index_documents(docs: Sequence[Document]) -> None:
    r"""Index documents into the RAG knowledge base.

    Args:
        docs: Sequence of Document instances to index

    Raises:
        ValueError: If documents are invalid
        RuntimeError: If indexing fails

    Example:
        >>> from egregora.data_primitives import Document, DocumentType
        >>> doc = Document(content="# Post\n\nContent", type=DocumentType.POST)
        >>> index_documents([doc])

    """
    backend = get_backend()
    backend.index_documents(docs)


def search(request: RAGQueryRequest) -> RAGQueryResponse:
    """Execute vector similarity search.

    Args:
        request: Query parameters (text, top_k, filters)

    Returns:
        Response containing ranked RAGHit results

    Raises:
        ValueError: If query parameters are invalid
        RuntimeError: If search fails

    Example:
        >>> request = RAGQueryRequest(text="search query", top_k=5)
        >>> response = search(request)
        >>> for hit in response.hits:
        ...     print(f"{hit.score:.2f}: {hit.text[:50]}")

    """
    backend = get_backend()
    return backend.query(request)


__all__ = [
    "RAGBackend",
    "RAGHit",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "get_backend",
    "index_documents",
    "search",
    # DuckDB integration (import from duckdb_integration module)
]
