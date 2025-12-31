"""Document chunking and ingestion for RAG (V3).

Port of V2 chunking logic to V3, enabling robust RAG support.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Sequence

from egregora_v3.core.types import Document, RAGChunk
from egregora_v3.core.utils import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_MAX_CHARS,
    simple_chunk_text,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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

        # Core metadata from document fields
        # Exclude fields that are large, irrelevant for search, or handled separately
        exclude_fields = {"content", "id"}
        doc_metadata = doc.model_dump(mode="json", exclude=exclude_fields)

        for i, piece in enumerate(pieces):
            chunk_id = f"{doc.id}:{i}"

            # Combine document metadata with chunk-specific info
            chunk_metadata = {
                **doc_metadata,
                "chunk_index": i,
            }

            chunks.append(
                RAGChunk(
                    chunk_id=chunk_id,
                    document_id=doc.id,
                    text=piece,
                    metadata=chunk_metadata,
                )
            )

    return chunks
