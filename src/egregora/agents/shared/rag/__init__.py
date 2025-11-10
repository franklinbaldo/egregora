"""RAG system for blog post and media indexing and retrieval.

DuckDB-based vector store for context-aware post enrichment and media search.
Uses Google Gemini embedding models (default: gemini-embedding-001, 768 dimensions).

**Requires GOOGLE_API_KEY** - RAG features depend on Gemini embeddings API.
Use `is_rag_available()` to check if RAG can be enabled.

The embedding model is configurable via ModelConfig. See config.model.DEFAULT_EMBEDDING_MODEL
and config.model.EMBEDDING_DIM for the embedding dimensionality.

Documentation:
- RAG Feature: docs/features/rag.md
- API Reference: docs/reference/api.md#rag-system
"""

import os

from egregora.agents.shared.rag.pydantic_helpers import (
    build_rag_context_for_writer,
    find_relevant_docs,
    format_rag_context,
)
from egregora.agents.shared.rag.retriever import (
    index_all_media,
    index_media_enrichment,
    index_post,
    query_media,
    query_similar_posts,
)
from egregora.agents.shared.rag.store import VectorStore


def is_rag_available() -> bool:
    """Check if RAG features are available (GOOGLE_API_KEY is set).

    RAG requires Google Gemini API for generating embeddings.
    Without an API key, indexing and retrieval operations will fail.

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    Example:
        >>> if is_rag_available():
        ...     store = VectorStore("chunks.parquet")
        ...     results = query_similar_posts(...)
        ... else:
        ...     print("RAG disabled - no GOOGLE_API_KEY")

    """
    return os.environ.get("GOOGLE_API_KEY") is not None


__all__ = [
    "VectorStore",
    "build_rag_context_for_writer",
    "find_relevant_docs",
    "format_rag_context",
    "index_all_media",
    "index_media_enrichment",
    "index_post",
    "is_rag_available",
    "query_media",
    "query_similar_posts",
]
