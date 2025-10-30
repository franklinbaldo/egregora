"""RAG system for blog post and media indexing and retrieval.

DuckDB-based vector store for context-aware post enrichment and media search.
Uses Google's text-embedding-004 model (3072 dimensions).

Documentation:
- RAG Feature: docs/features/rag.md
- API Reference: docs/reference/api.md#rag-system
"""

from .retriever import (
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
]
