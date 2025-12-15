"""Document chunking and ingestion for RAG (V3 Port).

Converts pipeline Documents (V2 or V3) into text chunks suitable for embedding and retrieval.
Uses simple whitespace-based chunking for reliability and simplicity.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from egregora_v3.core.types import DocumentType

logger = logging.getLogger(__name__)

# Chunking constants
DEFAULT_MAX_CHARS = 800  # Conservative default for manageable chunks
DEFAULT_CHUNK_OVERLAP = 200  # Overlap between chunks to preserve context


class ChunkableDocument(Protocol):
    """Protocol matching both V2 and V3 Documents."""
    content: str | bytes | None

    # V2 uses type/document_id, V3 uses doc_type/id
    # We can't easily express "one or the other" in Protocol properties without union
    # so we'll handle access dynamically.


@dataclass
class RAGChunk:
    """Internal representation of a RAG chunk."""

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
    doc: Any,  # Duck-typed for V2/V3 compatibility
    max_chars: int = DEFAULT_MAX_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    indexable_types: set[str] | None = None,
) -> list[RAGChunk]:
    """Convert a pipeline Document into one or more text chunks for RAG.

    Filtering:
        - Skips non-text content (bytes)
        - Only indexes specified document types (defaults to POST only)

    Chunking:
        - Overlapping chunks preserve context across boundaries
        - Default 200 char overlap prevents information loss

    Args:
        doc: Document instance to chunk (V2 or V3)
        max_chars: Maximum characters per chunk
        chunk_overlap: Characters to overlap between chunks
        indexable_types: Set of DocumentType values to index (default: {DocumentType.POST})

    Returns:
        List of RAGChunk instances

    """
    # Duck typing for V2/V3 compatibility
    content = getattr(doc, "content", None)

    # Skip binary content or empty
    if content is None or isinstance(content, bytes):
        return []

    # Resolve Type
    # V2: doc.type (Enum), V3: doc.doc_type (Enum)
    doc_type_val = getattr(doc, "type", getattr(doc, "doc_type", None))
    # Normalize to string
    doc_type_str = str(doc_type_val.value) if hasattr(doc_type_val, "value") else str(doc_type_val)

    # Use default indexable types if not provided
    if indexable_types is None:
        indexable_types = {DocumentType.POST.value}
        # Optionally include NOTE if it exists
        if hasattr(DocumentType, "NOTE"):
            indexable_types.add(DocumentType.NOTE.value)

    # Normalize input set to strings if they are enums
    normalized_types = set()
    for t in indexable_types:
        normalized_types.add(str(t.value) if hasattr(t, "value") else str(t))

    if doc_type_str not in normalized_types:
        return []

    # Resolve ID
    # V2: doc.document_id, V3: doc.id
    doc_id = getattr(doc, "document_id", getattr(doc, "id", None))
    if not doc_id:
        logger.warning("Skipping document with no ID: %s", getattr(doc, "title", "Untitled"))
        return []

    # Chunk the text with overlap
    pieces = _simple_chunk_text(content, max_chars=max_chars, overlap=chunk_overlap)

    chunks: list[RAGChunk] = []

    # Resolve metadata
    doc_metadata = getattr(doc, "metadata", getattr(doc, "internal_metadata", {})) or {}
    suggested_path = getattr(doc, "suggested_path", None)
    created_at = getattr(doc, "created_at", None)
    source_window = getattr(doc, "source_window", None)

    for i, piece in enumerate(pieces):
        chunk_id = f"{doc_id}:{i}"

        # Build metadata for this chunk
        metadata = {
            "document_id": doc_id,
            "type": doc_type_str,
            "suggested_path": suggested_path,
            "chunk_index": i,
        }

        if created_at:
            metadata["created_at"] = created_at.isoformat()
        if source_window:
            metadata["source_window"] = source_window

        # Merge in document metadata
        if doc_metadata:
            metadata.update(doc_metadata)

        chunks.append(
            RAGChunk(
                chunk_id=chunk_id,
                document_id=doc_id,
                text=piece,
                metadata=metadata,
            )
        )

    return chunks


def chunks_from_documents(
    docs: Sequence[Any],
    max_chars: int = DEFAULT_MAX_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    indexable_types: set[Any] | None = None,
) -> list[RAGChunk]:
    """Convert multiple Documents into chunks.

    Args:
        docs: Sequence of Document instances
        max_chars: Maximum characters per chunk
        chunk_overlap: Characters to overlap between chunks
        indexable_types: Set of DocumentType values to index (default: {DocumentType.POST})

    Returns:
        List of RAGChunk instances from all documents

    """
    chunks: list[RAGChunk] = []
    for doc in docs:
        chunks.extend(
            chunks_from_document(
                doc,
                max_chars=max_chars,
                chunk_overlap=chunk_overlap,
                indexable_types=indexable_types,
            )
        )
    logger.info("Chunked %d documents into %d chunks", len(docs), len(chunks))
    return chunks
