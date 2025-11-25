r"""RAG (Retrieval-Augmented Generation) package for Egregora.

This package provides chunking, embedding, vector storage, and retrieval
functionality for the RAG knowledge system.

Architecture:
    - chunker: Text chunking with token limits and overlap
    - embedder: Google GenAI embedding generation
    - store: Vector storage (DuckDB VSS + Parquet)
    - indexing: Document indexing operations
    - retriever: Similarity search and retrieval

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

    Storage:
        - VectorStore: Vector storage with DuckDB VSS
        - DatasetMetadata: Metadata container for vector datasets

    Indexing:
        - index_document: Index a Document for RAG
        - index_documents_for_rag: Batch index Documents
        - index_post: Index a post file
        - index_all_media: Index all media enrichments
        - index_media_enrichment: Index single media enrichment

    Retrieval:
        - query_similar_posts: Retrieve similar posts
        - query_media: Retrieve media enrichments
        - format_rag_context: Format retrieval results

Example:
    >>> from egregora.agents.shared.rag import chunk_from_document, embed_chunks, VectorStore
    >>> from egregora.data_primitives import Document, DocumentType
    >>>
    >>> # Chunk a document
    >>> doc = Document(content="# Post\\n\\nContent", type=DocumentType.POST)
    >>> chunks = chunk_from_document(doc)
    >>>
    >>> # Embed the chunks
    >>> texts = [chunk["content"] for chunk in chunks]
    >>> embeddings = embed_chunks(texts, model="models/text-embedding-004")
    >>>
    >>> # Store in vector store
    >>> store = VectorStore(parquet_path, storage=storage_manager)
    >>> # (indexing operations...)

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
from egregora.agents.shared.rag.indexing import (
    MediaEnrichmentMetadata,
    index_all_media,
    index_document,
    index_documents_for_rag,
    index_media_enrichment,
    index_post,
    index_specific_documents,
)
from egregora.agents.shared.rag.retriever import (
    format_rag_context,
    query_media,
    query_similar_posts,
)
from egregora.agents.shared.rag.store import (
    DatasetMetadata,
    VectorStore,
)

__all__ = [
    # Storage & Retrieval
    "DatasetMetadata",
    # Indexing
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
    "index_all_media",
    "index_document",
    "index_documents_for_rag",
    "index_media_enrichment",
    "index_post",
    "index_specific_documents",
    "is_rag_available",
    "parse_post",
    # Retrieval
    "query_media",
    "query_similar_posts",
]
