"""Document chunking and ingestion for RAG.

Converts pipeline Documents into text chunks suitable for embedding and retrieval.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from egregora.data_primitives.document import Document, DocumentType

logger = logging.getLogger(__name__)

# Chunking constants
DEFAULT_MAX_CHARS = 800  # Conservative default for manageable chunks
DEFAULT_MAX_TOKENS = 1800  # Maximum tokens per chunk (for LangChain splitter)
DEFAULT_OVERLAP_TOKENS = 150  # Overlap between chunks for context


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
    """Very simple chunking: split text into ~max_chars chunks on whitespace.

    This is a fallback chunker. For production use, consider using the
    LangChain-based chunker for better quality.

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


def _langchain_chunk_text(
    text: str, max_tokens: int = DEFAULT_MAX_TOKENS, overlap_tokens: int = DEFAULT_OVERLAP_TOKENS
) -> list[str]:
    """Chunk text using LangChain's RecursiveCharacterTextSplitter.

    More sophisticated than simple chunking - respects sentence boundaries,
    paragraphs, and token limits.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Tokens of overlap between chunks

    Returns:
        List of text chunks

    """
    if not text.strip():
        return []

    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",  # Standard encoder compatible with Gemini
        chunk_size=max_tokens,
        chunk_overlap=overlap_tokens,
        separators=[
            "\n\n",  # Split by paragraph first
            "\n",  # Then by line
            " ",  # Then by word
            "",  # Finally by character
        ],
    )
    return text_splitter.split_text(text)


def chunks_from_document(
    doc: Document, max_chars: int = DEFAULT_MAX_CHARS, *, use_langchain: bool = False
) -> list[_RAGChunk]:
    """Convert a pipeline Document into one or more text chunks for RAG.

    Filtering:
        - Skips non-text content (bytes)
        - Only indexes POST and NOTE document types by default

    Args:
        doc: Document instance to chunk
        max_chars: Maximum characters per chunk (for simple chunker)
        use_langchain: Use LangChain splitter (default: True, better quality)

    Returns:
        List of _RAGChunk instances

    """
    # Skip binary content
    if isinstance(doc.content, bytes):
        return []

    # Only index certain document types
    # Adjust this filter based on your needs
    indexable_types = {DocumentType.POST}
    if hasattr(DocumentType, "NOTE"):
        indexable_types.add(DocumentType.NOTE)

    if doc.type not in indexable_types:
        return []

    text = doc.content

    # Choose chunking strategy
    if use_langchain:
        pieces = _langchain_chunk_text(text, max_tokens=DEFAULT_MAX_TOKENS)
    else:
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
    docs: Sequence[Document], max_chars: int = DEFAULT_MAX_CHARS, *, use_langchain: bool = False
) -> list[_RAGChunk]:
    """Convert multiple Documents into chunks.

    Args:
        docs: Sequence of Document instances
        max_chars: Maximum characters per chunk (for simple chunker)
        use_langchain: Use LangChain splitter (default: True)

    Returns:
        List of _RAGChunk instances from all documents

    """
    chunks: list[_RAGChunk] = []
    for doc in docs:
        chunks.extend(chunks_from_document(doc, max_chars=max_chars, use_langchain=use_langchain))
    return chunks


__all__ = [
    "chunks_from_document",
    "chunks_from_documents",
]
