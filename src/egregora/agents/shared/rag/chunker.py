"""Text chunking logic for RAG knowledge system.

Splits documents into manageable chunks for embedding and retrieval.
Works with Document instances from the pipeline.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from egregora.utils.frontmatter_utils import parse_frontmatter

if TYPE_CHECKING:
    from egregora.data_primitives import Document

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: ~4 chars per token)."""
    # Centralized implementation
    from egregora.agents.model_limits import estimate_tokens as _estimate  # noqa: PLC0415

    return _estimate(text)


def chunk_markdown(content: str, max_tokens: int = 1800, overlap_tokens: int = 150) -> list[str]:
    r"""Chunk markdown content respecting token limits.

    Splits content into paragraphs and groups them into chunks that fit within
    token limits, with optional overlap between chunks for context preservation.

    Args:
        content: Markdown text to chunk
        max_tokens: Maximum tokens per chunk (default: 1800)
        overlap_tokens: Tokens of overlap between chunks (default: 150)

    Returns:
        List of markdown text chunks

    Example:
        >>> chunks = chunk_markdown("# Title\\n\\nPara 1\\n\\nPara 2", max_tokens=100)
        >>> len(chunks) >= 1
        True

    """
    paragraphs = content.split("\n\n")
    chunks = []
    current_chunk: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        para = paragraph.strip()
        if not para:
            continue

        para_tokens = estimate_tokens(para)

        if current_tokens + para_tokens > max_tokens and current_chunk:
            # Emit current chunk
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)

            # Create overlap from end of previous chunk
            overlap_paras: list[str] = []
            overlap_tokens_count = 0
            for prev_para in reversed(current_chunk):
                prev_tokens = estimate_tokens(prev_para)
                if overlap_tokens_count + prev_tokens <= overlap_tokens:
                    overlap_paras.insert(0, prev_para)
                    overlap_tokens_count += prev_tokens
                else:
                    break

            current_chunk = overlap_paras
            current_tokens = overlap_tokens_count

        current_chunk.append(para)
        current_tokens += para_tokens

    # Emit final chunk
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append(chunk_text)

    return chunks


def parse_post(post_path: Path) -> tuple[dict[str, Any], str]:
    """Parse blog post with YAML frontmatter.

    Args:
        post_path: Path to markdown file with frontmatter

    Returns:
        Tuple of (metadata dict, body text)

    """
    content = post_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)

    # Extract slug from filename if not in frontmatter
    if "slug" not in metadata:
        filename = post_path.stem
        match = re.match("\\d{4}-\\d{2}-\\d{2}-(.+)", filename)
        if match:
            metadata["slug"] = match.group(1)
        else:
            metadata["slug"] = filename

    # Generate title from slug if not in frontmatter
    if "title" not in metadata:
        metadata["title"] = metadata["slug"].replace("-", " ").title()

    # Extract date from filename if not in frontmatter
    if "date" not in metadata:
        filename = post_path.stem
        match = re.match("(\\d{4}-\\d{2}-\\d{2})", filename)
        if match:
            metadata["date"] = match.group(1)
        else:
            metadata["date"] = None

    return (metadata, body)


def chunk_document(post_path: Path, max_tokens: int = 1800) -> list[dict[str, Any]]:
    """Chunk a blog post file into indexable chunks.

    Args:
        post_path: Path to markdown file
        max_tokens: Maximum tokens per chunk (default: 1800)

    Returns:
        List of chunk dicts with content, metadata, and indices

    """
    metadata, content = parse_post(post_path)
    text_chunks = chunk_markdown(content, max_tokens=max_tokens)

    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        chunks.append(
            {
                "content": chunk_text,
                "chunk_index": i,
                "post_slug": metadata["slug"],
                "post_title": metadata["title"],
                "metadata": metadata,
            }
        )

    logger.info("Chunked %s into %s chunks", post_path.name, len(chunks))
    return chunks


def chunk_from_document(document: Document, max_tokens: int = 1800) -> list[dict[str, Any]]:
    r"""Chunk a Document object into indexable chunks.

    This is the primary chunking function for Document-based RAG indexing.
    Output adapters provide Documents, which are chunked for embedding.

    Args:
        document: Document instance to chunk
        max_tokens: Maximum tokens per chunk (default: 1800)

    Returns:
        List of chunk dicts with content, metadata, document_id, and indices

    Example:
        >>> from egregora.data_primitives import Document, DocumentType
        >>> doc = Document(
        ...     content="# Post\\n\\nContent here",
        ...     type=DocumentType.POST,
        ...     metadata={"slug": "my-post", "title": "My Post"}
        ... )
        >>> chunks = chunk_from_document(doc)
        >>> chunks[0]["document_id"] == doc.document_id
        True

    """
    # Extract slug and title from metadata
    metadata = document.metadata
    slug = metadata.get("slug", document.document_id[:8])
    title = metadata.get("title", slug.replace("-", " ").title())

    # Handle binary content (should be str for text documents)
    content = document.content
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    # Chunk the document content
    text_chunks = chunk_markdown(content, max_tokens=max_tokens)

    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        chunks.append(
            {
                "content": chunk_text,
                "chunk_index": i,
                "post_slug": slug,
                "post_title": title,
                "metadata": metadata,
                "document_id": document.document_id,  # Include content-addressed ID
            }
        )

    logger.info("Chunked Document %s into %s chunks", document.document_id[:8], len(chunks))
    return chunks


__all__ = [
    "chunk_document",
    "chunk_from_document",
    "chunk_markdown",
    "estimate_tokens",
    "parse_post",
]
