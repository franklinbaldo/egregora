"""Document chunking and ingestion for RAG (V3).

Port of V2 chunking logic to V3, enabling robust RAG support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

from egregora_v3.core.types import Document, DocumentType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Chunking constants
DEFAULT_MAX_CHARS = 800
DEFAULT_CHUNK_OVERLAP = 200


@dataclass
class RAGChunk:
    """Internal representation of a RAG chunk."""
    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any]


def simple_chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Simple chunking: split text into ~max_chars chunks with overlap."""
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    overlap = min(overlap, max_chars // 2)
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    # Overlap buffer
    overlap_words: list[str] = []
    overlap_len = 0

    for w in words:
        word_len = len(w) + 1  # +1 for space

        if current_len + word_len > max_chars and current:
            chunk_text = " ".join(current)
            chunks.append(chunk_text)

            # Build overlap from end of current chunk
            overlap_words = []
            overlap_len = 0
            for overlap_word in reversed(current):
                overlap_word_len = len(overlap_word) + 1
                if overlap_len + overlap_word_len <= overlap:
                    overlap_words.append(overlap_word)
                    overlap_len += overlap_word_len
                else:
                    break
            overlap_words.reverse()

            current = overlap_words.copy()
            current_len = overlap_len

        current.append(w)
        current_len += word_len

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunks_from_documents(
    docs: Sequence[Document],
    max_chars: int = DEFAULT_MAX_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[RAGChunk]:
    """Convert multiple Documents into chunks."""
    chunks: list[RAGChunk] = []

    for doc in docs:
        if not doc.content:
            continue

        # Only index text content
        if not isinstance(doc.content, str):
            continue

        # V3 Type Filtering could happen here, or upstream
        # For now, we index everything passed to us

        text = doc.content
        pieces = simple_chunk_text(text, max_chars=max_chars, overlap=chunk_overlap)

        for i, piece in enumerate(pieces):
            chunk_id = f"{doc.id}:{i}"

            # Base metadata
            metadata = {
                "document_id": doc.id,
                "doc_type": doc.doc_type.value,
                "title": doc.title,
                "chunk_index": i,
                "updated": doc.updated.isoformat(),
            }

            # Merge internal metadata if safe
            if doc.internal_metadata:
                 # Filter out complex objects if necessary, but DuckDB/LanceDB handles JSON
                 metadata.update(doc.internal_metadata)

            chunks.append(RAGChunk(
                chunk_id=chunk_id,
                document_id=doc.id,
                text=piece,
                metadata=metadata
            ))

    return chunks
