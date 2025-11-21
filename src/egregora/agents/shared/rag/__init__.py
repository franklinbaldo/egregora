r"""RAG (Retrieval-Augmented Generation) package for Egregora.

This package provides chunking, embedding, vector storage, and retrieval
functionality for the RAG knowledge system.

Architecture:
    - chunker: Text chunking with token limits and overlap
    - embedder: Google GenAI embedding generation
    - store: Vector storage (DuckDB VSS) - TODO: extract from knowledge.rag
    - indexing: Document indexing operations - TODO: extract from knowledge.rag
    - retriever: Similarity search and retrieval - TODO: extract from knowledge.rag

Phase 2 Progress:
    ✅ Package structure created
    ✅ chunker.py extracted (chunk_markdown, chunk_from_document)
    ✅ embedder.py extracted (embed_text, embed_chunks, embed_query_text)
    🔄 store.py - TODO: Extract VectorStore class from knowledge.rag
    🔄 indexing.py - TODO: Extract index_document, index_documents_for_rag
    🔄 retriever.py - TODO: Extract query_similar_posts, query_media

Public API:
    Chunking:
        - chunk_from_document: Chunk Documents for indexing (primary)
        - chunk_markdown: Chunk markdown text
        - chunk_document: Chunk file paths
        - estimate_tokens: Estimate token count

    Embedding:
        - embed_chunks: Embed text chunks for indexing
        - embed_query_text: Embed query for retrieval
        - embed_text: Embed single text
        - embed_texts_in_batch: Batch embedding
        - is_rag_available: Check if API key is available

    Storage (from knowledge.rag - temporary):
        - VectorStore: Vector storage with DuckDB VSS
        - index_document: Index a Document for RAG
        - index_documents_for_rag: Batch index Documents
        - query_similar_posts: Retrieve similar posts
        - query_media: Retrieve media enrichments
        - format_rag_context: Format retrieval results

Example:
    >>> from egregora.agents.shared.rag import chunk_from_document, embed_chunks
    >>> from egregora.data_primitives import Document, DocumentType
    >>>
    >>> # Chunk a document
    >>> doc = Document(content="# Post\\n\\nContent", type=DocumentType.POST)
    >>> chunks = chunk_from_document(doc)
    >>>
    >>> # Embed the chunks
    >>> texts = [chunk["content"] for chunk in chunks]
    >>> embeddings = embed_chunks(texts, model="models/text-embedding-004")

"""

from egregora.agents.shared.rag.chunker import (
    chunk_document,
    chunk_from_document,
    chunk_markdown,
    estimate_tokens,
    parse_post,
)
from egregora.agents.shared.rag.embedder import (
    embed_chunks,
    embed_query_text,
    embed_text,
    embed_texts_in_batch,
    is_rag_available,
)

# Temporary: Import from knowledge.rag until extraction complete
from egregora.knowledge.rag import (
    VectorStore,
    format_rag_context,
    index_document,
    index_documents_for_rag,
    query_media,
    query_similar_posts,
)

__all__ = [
    # Storage & Retrieval (temporary from knowledge.rag)
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
    "index_document",
    "index_documents_for_rag",
    "is_rag_available",
    "parse_post",
    "query_media",
    "query_similar_posts",
]
