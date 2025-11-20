"""Shared RAG utilities for agents.

This package provides unified access to RAG functionality:
- **Core**: Chunking and Embedding (Chunk, Embed)
- **Operations**: Indexing and Retrieval (Index, Retrieve)
- **Store**: Vector Store management
- **Helpers**: Pydantic integration

Structure:
    rag/
    ├── core.py       # Chunking & Embedding (Input Processing)
    ├── operations.py # Indexing & Retrieval (Workflow Logic)
    ├── store.py      # Vector Store (State Management)
    └── pydantic_helpers.py
"""

from egregora.agents.shared.rag.core import (
    chunk_document,
    chunk_from_document,
    embed_chunks,
    embed_query_text,
    embed_text,
    embed_texts_in_batch,
    is_rag_available,
)
from egregora.agents.shared.rag.operations import (
    index_all_media,
    index_document,
    index_documents_for_rag,
    index_media_enrichment,
    index_post,
    query_media,
    query_similar_posts,
)
from egregora.agents.shared.rag.store import VectorStore

__all__ = [
    "VectorStore",
    "chunk_document",
    "chunk_from_document",
    "embed_chunks",
    "embed_query_text",
    "embed_text",
    "embed_texts_in_batch",
    "index_all_media",
    "index_document",
    "index_documents_for_rag",
    "index_media_enrichment",
    "index_post",
    "is_rag_available",
    "query_media",
    "query_similar_posts",
]
