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


@dataclass
class _RAGChunk:
    """Internal representation of a RAG chunk.

    Not exported - used only within the RAG package.
    """

    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any]


def _simple_chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Simple chunking: split text into ~max_chars chunks on whitespace.

    Splits on word boundaries to avoid breaking mid-word.
    For better semantic chunking, consider using a more sophisticated
    approach in the future.

    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk

    Returns:
        List of text chunks

    """
    if len(text) <= max_chars:
        return [text]

    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for w in words:
        if current_len + len(w) + 1 > max_chars and current:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(w)
        current_len += len(w) + 1

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunks_from_document(
    doc: Document,
    max_chars: int = DEFAULT_MAX_CHARS,
    indexable_types: set[DocumentType] | None = None,
) -> list[_RAGChunk]:
    """Convert a pipeline Document into one or more text chunks for RAG.

    Filtering:
        - Skips non-text content (bytes)
        - Only indexes specified document types (defaults to POST only)

    Args:
        doc: Document instance to chunk
        max_chars: Maximum characters per chunk
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

    # Chunk the text
    pieces = _simple_chunk_text(text, max_chars=max_chars)

    chunks: list[_RAGChunk] = []

    for i, piece in enumerate(pieces):
        chunk_id = f"{doc.document_id}:{i}"

        # Build metadata for this chunk
        metadata = {
            "document_id": doc.document_id,
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
                document_id=doc.document_id,
                text=piece,
                metadata=metadata,
            )
        )

    logger.info("Chunked Document %s into %d chunks", doc.document_id[:8], len(chunks))
    return chunks


def chunks_from_documents(
    docs: Sequence[Document],
    max_chars: int = DEFAULT_MAX_CHARS,
    indexable_types: set[DocumentType] | None = None,
) -> list[_RAGChunk]:
    """Convert multiple Documents into chunks.

    Args:
        docs: Sequence of Document instances
        max_chars: Maximum characters per chunk
        indexable_types: Set of DocumentType values to index (default: {DocumentType.POST})

    Returns:
        List of _RAGChunk instances from all documents

    """
    chunks: list[_RAGChunk] = []
    for doc in docs:
        chunks.extend(chunks_from_document(doc, max_chars=max_chars, indexable_types=indexable_types))
    return chunks


__all__ = [
    "chunks_from_document",
    "chunks_from_documents",
]
