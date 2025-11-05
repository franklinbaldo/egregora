"""RAG system for blog post and media indexing and retrieval.

DuckDB-based vector store for context-aware post enrichment and media search.
Uses Google Gemini embedding models (default: gemini-embedding-001, 3072 dimensions).

The embedding model is configurable via ModelConfig. See config.model.DEFAULT_EMBEDDING_MODEL
and config.model.KNOWN_EMBEDDING_DIMENSIONS for supported models and their dimensions.

Documentation:
- RAG Feature: docs/features/rag.md
- API Reference: docs/reference/api.md#rag-system
"""

from egregora.rag.pydantic_helpers import (
    build_rag_context_for_writer,
    find_relevant_docs,
    format_rag_context,
)
from egregora.rag.retriever import (
    index_all_media,
    index_media_enrichment,
    index_post,
    query_media,
    query_similar_posts,
)

from .store import VectorStore

__all__ = [
    "VectorStore",
    "query_similar_posts",
    "index_post",
    "index_media_enrichment",
    "index_all_media",
    "query_media",
    "find_relevant_docs",
    "format_rag_context",
    "build_rag_context_for_writer",
]
