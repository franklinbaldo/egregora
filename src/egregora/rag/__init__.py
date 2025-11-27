"""RAG (Retrieval-Augmented Generation) package for Egregora.

This package provides a clean RAG abstraction with pluggable backends:

- **LanceDBRAGBackend**: New LanceDB-based implementation (recommended)
- **DuckDBRAGBackend**: Legacy DuckDB VSS wrapper (deprecated)

Public API:
    - get_backend(): Get the configured RAG backend
    - index_documents(): Index documents into RAG
    - search(): Execute vector similarity search
    - RAGHit, RAGQueryRequest, RAGQueryResponse: Core data models

Configuration:
    Set backend via .egregora/config.yml:
    ```yaml
    rag:
      backend: lancedb  # or "duckdb_legacy"
      top_k: 5
    ```

Example:
    >>> from egregora.rag import index_documents, search, RAGQueryRequest
    >>> from egregora.data_primitives import Document, DocumentType
    >>>
    >>> # Index documents
    >>> doc = Document(content="# Post\\n\\nContent", type=DocumentType.POST)
    >>> index_documents([doc])
    >>>
    >>> # Search
    >>> request = RAGQueryRequest(text="search query", top_k=5)
    >>> response = search(request)
    >>> for hit in response.hits:
    ...     print(f"{hit.score:.2f}: {hit.text[:50]}")

"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from egregora.data_primitives.document import Document

from .backend import RAGBackend
from .models import RAGHit, RAGQueryRequest, RAGQueryResponse

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Global backend instance (lazy-initialized)
_backend: RAGBackend | None = None


def _create_backend() -> RAGBackend:
    """Create RAG backend based on configuration.

    Reads from egregora.config.settings to determine which backend to use.

    Returns:
        Configured RAGBackend instance

    Raises:
        ValueError: If backend configuration is invalid
        RuntimeError: If backend initialization fails

    """
    # Import here to avoid circular dependency
    # Try to load config from current directory
    from pathlib import Path

    from egregora.config.settings import load_egregora_config

    try:
        config = load_egregora_config(Path.cwd())
    except Exception as e:
        logger.warning("Failed to load config, using defaults: %s", e)
        # Fall back to default config
        from egregora.config.settings import EgregoraConfig

        config = EgregoraConfig()

    rag_settings = config.rag
    backend_type = getattr(rag_settings, "backend", "duckdb_legacy")

    if backend_type == "lancedb":
        logger.info("Creating LanceDB RAG backend")
        return _create_lancedb_backend(config)
    if backend_type == "duckdb_legacy":
        logger.info("Creating DuckDB legacy RAG backend")
        return _create_duckdb_backend(config)

    msg = f"Unknown RAG backend: {backend_type}"
    raise ValueError(msg)


def _create_lancedb_backend(config: Any) -> RAGBackend:  # type: ignore[misc]
    """Create LanceDB backend.

    Args:
        config: EgregoraConfig instance

    Returns:
        LanceDBRAGBackend instance

    """
    from pathlib import Path

    from egregora.agents.shared.rag.embedder import embed_texts_in_batch

    from .lancedb_backend import LanceDBRAGBackend

    # Determine lancedb_dir from config
    lancedb_dir = Path.cwd() / ".egregora" / "lancedb"
    if hasattr(config, "paths") and hasattr(config.paths, "lancedb_dir"):
        lancedb_dir = Path.cwd() / config.paths.lancedb_dir

    # Get embedding model
    embedding_model = config.models.embedding

    # Create embedding function that wraps the existing embedder
    def embed_fn(texts: Sequence[str]) -> list[list[float]]:
        return embed_texts_in_batch(list(texts), model=embedding_model)

    return LanceDBRAGBackend(
        db_dir=lancedb_dir,
        table_name="rag_embeddings",
        embed_fn=embed_fn,
        top_k_default=config.rag.top_k,
    )


def _create_duckdb_backend(config: Any) -> RAGBackend:  # type: ignore[misc]
    """Create DuckDB legacy backend.

    Args:
        config: EgregoraConfig instance

    Returns:
        DuckDBRAGBackend instance

    """
    from pathlib import Path

    from egregora.database.duckdb_manager import DuckDBStorageManager

    from .duckdb_backend import DuckDBRAGBackend

    # Determine rag_dir from config
    rag_dir = Path.cwd() / ".egregora" / "rag"
    if hasattr(config, "paths") and hasattr(config.paths, "rag_dir"):
        rag_dir = Path.cwd() / config.paths.rag_dir

    parquet_path = rag_dir / "chunks.parquet"

    # Create storage manager
    # For now, use default connection
    storage = DuckDBStorageManager()

    return DuckDBRAGBackend(
        parquet_path=parquet_path,
        storage=storage,
        embedding_model=config.models.embedding,
        top_k_default=config.rag.top_k,
    )


def get_backend() -> RAGBackend:
    """Get the configured RAG backend.

    Lazily initializes the backend on first call.

    Returns:
        RAGBackend instance

    Raises:
        ValueError: If backend configuration is invalid
        RuntimeError: If backend initialization fails

    """
    global _backend  # noqa: PLW0603
    if _backend is None:
        _backend = _create_backend()
    return _backend


def index_documents(docs: Sequence[Document]) -> None:
    """Index documents into the RAG knowledge base.

    Args:
        docs: Sequence of Document instances to index

    Raises:
        ValueError: If documents are invalid
        RuntimeError: If indexing fails

    Example:
        >>> from egregora.data_primitives import Document, DocumentType
        >>> doc = Document(content="# Post\\n\\nContent", type=DocumentType.POST)
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
]
