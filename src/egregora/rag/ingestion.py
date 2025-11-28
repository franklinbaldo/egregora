"""Document chunking and ingestion for RAG.

Converts pipeline Documents into text chunks suitable for embedding and retrieval.
Uses simple whitespace-based chunking for reliability and simplicity.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from egregora.data_primitives.document import Document, DocumentType

logger = logging.getLogger(__name__)

# Chunking constants
DEFAULT_MAX_CHARS = 800  # Conservative default for manageable chunks
DEFAULT_CHUNK_OVERLAP = 200  # Overlap between chunks to preserve context


@dataclass
class _RAGChunk:
    """Internal representation of a RAG chunk.

    Not exported - used only within the RAG package.
    """

    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any]


def _simple_chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Simple chunking: split text into ~max_chars chunks with overlap on whitespace.

    Splits on word boundaries to avoid breaking mid-word.
    Overlapping chunks ensure context is preserved across boundaries.

    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk
        overlap: Number of characters to overlap between chunks

    Returns:
        List of text chunks with overlap

    """
    if len(text) <= max_chars:
        return [text]

    # Ensure overlap is less than max_chars
    overlap = min(overlap, max_chars // 2)

    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    # Track words for overlap
    overlap_words: list[str] = []
    overlap_len = 0

    for w in words:
        word_len = len(w) + 1  # +1 for space

        # Check if we need to start a new chunk
        if current_len + word_len > max_chars and current:
            # Save current chunk
            chunk_text = " ".join(current)
            chunks.append(chunk_text)

            # Build overlap from end of current chunk (O(n) not O(n²))
            overlap_words = []
            overlap_len = 0
            for overlap_word in reversed(current):
                overlap_word_len = len(overlap_word) + 1
                if overlap_len + overlap_word_len <= overlap:
                    overlap_words.append(overlap_word)  # O(1) append, not O(n) insert(0)
                    overlap_len += overlap_word_len
                else:
                    break
            # Reverse once at the end (O(n) once, not O(n) per word)
            overlap_words.reverse()

            # Start new chunk with overlap
            current = overlap_words.copy()
            current_len = overlap_len

        current.append(w)
        current_len += word_len

    # Add final chunk
    if current:
        chunks.append(" ".join(current))

    return chunks


def chunks_from_document(
    doc: Document,
    max_chars: int = DEFAULT_MAX_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    indexable_types: set[DocumentType] | None = None,
) -> list[_RAGChunk]:
    """Convert a pipeline Document into one or more text chunks for RAG.

    Filtering:
        - Skips non-text content (bytes)
        - Only indexes specified document types (defaults to POST only)

    Chunking:
        - Overlapping chunks preserve context across boundaries
        - Default 200 char overlap prevents information loss

    Args:
        doc: Document instance to chunk
        max_chars: Maximum characters per chunk
        chunk_overlap: Characters to overlap between chunks
        indexable_types: Set of DocumentType values to index (default: {DocumentType.POST})

    Returns:
        List of _RAGChunk instances

    """
    # Skip binary content
    if isinstance(doc.content, bytes):
        return []

    # Use default indexable types if not provided
    if indexable_types is None:
        indexable_types = {DocumentType.POST}
        # Optionally include NOTE if it exists
        if hasattr(DocumentType, "NOTE"):
            indexable_types = {DocumentType.POST, DocumentType.NOTE}

    if doc.type not in indexable_types:
        return []

    text = doc.content

    # Compute the document ID once to avoid repeated hashing for large documents
    doc_id = doc.document_id

    # Chunk the text with overlap
    pieces = _simple_chunk_text(text, max_chars=max_chars, overlap=chunk_overlap)

    chunks: list[_RAGChunk] = []

    for i, piece in enumerate(pieces):
        chunk_id = f"{doc_id}:{i}"

        # Build metadata for this chunk
        metadata = {
            "document_id": doc_id,
            "type": doc.type.value if hasattr(doc.type, "value") else str(doc.type),
            "suggested_path": doc.suggested_path,
            "created_at": doc.created_at.isoformat(),
            "source_window": doc.source_window,
            "chunk_index": i,
        }

        # Merge in document metadata
        if doc.metadata:
            metadata.update(doc.metadata)

        chunks.append(
            _RAGChunk(
                chunk_id=chunk_id,
                document_id=doc_id,
                text=piece,
                metadata=metadata,
            )
        )

    logger.info("Chunked Document %s into %d chunks", doc.document_id[:8], len(chunks))
    return chunks


def chunks_from_documents(
    docs: Sequence[Document],
    max_chars: int = DEFAULT_MAX_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    indexable_types: set[DocumentType] | None = None,
) -> list[_RAGChunk]:
    """Convert multiple Documents into chunks.

    Args:
        docs: Sequence of Document instances
        max_chars: Maximum characters per chunk
        chunk_overlap: Characters to overlap between chunks
        indexable_types: Set of DocumentType values to index (default: {DocumentType.POST})

    Returns:
        List of _RAGChunk instances from all documents

    """
    chunks: list[_RAGChunk] = []
    for doc in docs:
        chunks.extend(
            chunks_from_document(
                doc,
                max_chars=max_chars,
                chunk_overlap=chunk_overlap,
                indexable_types=indexable_types,
            )
        )
    return chunks


__all__ = [
    "chunks_from_document",
    "chunks_from_documents",
]
