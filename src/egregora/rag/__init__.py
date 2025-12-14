r"""RAG (Retrieval-Augmented Generation) package for Egregora.

This package provides a simple RAG implementation using LanceDB for vector storage,
with DuckDB integration for SQL-based analytics and filtering.

Public API:
    - create_rag_backend(): Factory to create a RAG backend
    - RAGHit, RAGQueryRequest, RAGQueryResponse: Core data models

DuckDB Integration:
    - search_to_table(): Convert RAG results to Ibis/DuckDB table
    - join_with_messages(): Join RAG results with message data
    - search_with_filters(): Vector search with SQL filtering

"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import DocumentType
from egregora.rag.backend import RAGBackend
from egregora.rag.embedding_router import EmbeddingRouter, create_embedding_router
from egregora.rag.lancedb_backend import LanceDBRAGBackend
from egregora.rag.models import RAGHit, RAGQueryRequest, RAGQueryResponse

logger = logging.getLogger(__name__)


def create_rag_backend(config: EgregoraConfig, site_root: Path | None = None) -> RAGBackend:
    """Create LanceDB RAG backend based on configuration.

    Args:
        config: Egregora configuration
        site_root: Root directory of the site (optional, defaults to CWD)

    Returns:
        LanceDBRAGBackend instance

    Raises:
        RuntimeError: If backend initialization fails

    """
    root = site_root or Path.cwd()

    # Determine lancedb_dir from config
    lancedb_dir = root / ".egregora" / "lancedb"
    if hasattr(config, "paths") and hasattr(config.paths, "lancedb_dir"):
        # If path is absolute, use it. If relative, resolve against root.
        configured_path = Path(config.paths.lancedb_dir)
        if configured_path.is_absolute():
            lancedb_dir = configured_path
        else:
            lancedb_dir = root / configured_path

    # Get embedding model
    rag_settings = config.rag
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

    # Create sync embedding function that uses the dual-queue router
    # IMPORTANT: Google Gemini embeddings are asymmetric - documents and queries
    # must use different task_type values for optimal retrieval quality.
    # The caller (LanceDBRAGBackend) is responsible for specifying the correct task_type.
    router: EmbeddingRouter | None = None

    def embed_fn(texts: Sequence[str], task_type: str) -> list[list[float]]:
        nonlocal router
        if router is None:
            router = create_embedding_router(
                model=embedding_model,
                api_key=None,
                max_batch_size=rag_settings.embedding_max_batch_size,
                timeout=rag_settings.embedding_timeout,
            )

        return router.embed(list(texts), task_type=task_type)

    logger.info("Creating LanceDB RAG backend at %s", lancedb_dir)
    return LanceDBRAGBackend(
        db_dir=lancedb_dir,
        table_name="rag_embeddings",
        embed_fn=embed_fn,
        indexable_types=indexable_types,
    )


__all__ = [
    "RAGBackend",
    "RAGHit",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "create_rag_backend",
]
