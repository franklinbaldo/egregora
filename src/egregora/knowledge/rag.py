"""Backward-compatible shim for RAG functionality.

DEPRECATED: This module re-exports from egregora.agents.shared.rag.
Please update imports to use the new location:

    from egregora.agents.shared.rag import VectorStore, embed_query_text, ...

This shim will be removed in a future version.
"""

from __future__ import annotations

import warnings

# Re-export all public API from new modular structure
from egregora.agents.shared.rag import (
    DatasetMetadata,
    MediaEnrichmentMetadata,
    VectorStore,
    chunk_document,
    chunk_from_document,
    chunk_markdown,
    embed_chunks,
    embed_query_text,
    embed_text,
    embed_texts_in_batch,
    estimate_tokens,
    format_rag_context,
    index_all_media,
    index_document,
    index_documents_for_rag,
    index_media_enrichment,
    index_post,
    is_rag_available,
    parse_post,
    query_media,
    query_similar_posts,
)

__all__ = [
    # Storage & Retrieval
    "DatasetMetadata",
    "MediaEnrichmentMetadata",
    "VectorStore",
    # Chunking
    "chunk_document",
    "chunk_from_document",
    "chunk_markdown",
    # Embedding
    "embed_chunks",
    "embed_query_text",
    "embed_text",
    "embed_texts_in_batch",
    "estimate_tokens",
    "format_rag_context",
    # Indexing
    "index_all_media",
    "index_document",
    "index_documents_for_rag",
    "index_media_enrichment",
    "index_post",
    "is_rag_available",
    "parse_post",
    # Retrieval
    "query_media",
    "query_similar_posts",
]


def __getattr__(name: str) -> object:
    """Emit deprecation warning for public API attribute access."""
    # Don't warn for module internals
    if name.startswith("__"):
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    # Only warn for public API attributes
    if name in __all__:
        warnings.warn(
            f"Importing '{name}' from egregora.knowledge.rag is deprecated. "
            f"Use 'from egregora.agents.shared.rag import {name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()[name]

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
