"""Document chunking and ingestion for RAG.

Converts pipeline Documents into text chunks suitable for embedding and retrieval.
Uses simple whitespace-based chunking for reliability and simplicity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from egregora.data_primitives.document import Document, DocumentType
from egregora.text.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_MAX_CHARS,
    simple_chunk_text,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


@dataclass
class _RAGChunk:
    """Internal representation of a RAG chunk.

    Not exported - used only within the RAG package.
    """

    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any]


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
    pieces = simple_chunk_text(text, max_chars=max_chars, overlap=chunk_overlap)
    if not pieces and text == "":
        pieces = [""]

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
