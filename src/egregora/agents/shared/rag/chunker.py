"""Document chunking for RAG system."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: ~4 chars per token).

    Gemini embedding limit: 2048 tokens
    We use 1800 tokens max per chunk for safety.
    """
    # Centralized implementation
    from egregora.agents.model_limits import estimate_tokens as _estimate

    return _estimate(text)


def chunk_markdown(content: str, max_tokens: int = 1800, overlap_tokens: int = 150) -> list[str]:
    r"""Chunk markdown content respecting token limits.

    Strategy:
    - Split on paragraph boundaries (\\\\n\\\\n)
    - Max 1800 tokens per chunk (safe under 2048 limit)
    - 150 token overlap between chunks for context

    Args:
        content: Markdown text
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap between consecutive chunks

    Returns:
        List of text chunks

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
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)
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
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append(chunk_text)
    return chunks


def parse_post(post_path: Path) -> tuple[dict[str, Any], str]:
    """Parse blog post with YAML frontmatter.

    Returns:
        (metadata_dict, content_string)

    """
    with post_path.open(encoding="utf-8") as f:
        post = frontmatter.load(f)
    metadata = dict(post.metadata)
    if "slug" not in metadata:
        filename = post_path.stem
        match = re.match("\\d{4}-\\d{2}-\\d{2}-(.+)", filename)
        if match:
            metadata["slug"] = match.group(1)
        else:
            metadata["slug"] = filename
    if "title" not in metadata:
        metadata["title"] = metadata["slug"].replace("-", " ").title()
    if "date" not in metadata:
        filename = post_path.stem
        match = re.match("(\\d{4}-\\d{2}-\\d{2})", filename)
        if match:
            metadata["date"] = match.group(1)
        else:
            metadata["date"] = None
    return (metadata, post.content)


def chunk_document(post_path: Path, max_tokens: int = 1800) -> list[dict[str, Any]]:
    """Chunk a blog post into indexable chunks.

    Args:
        post_path: Path to markdown file with YAML frontmatter
        max_tokens: Max tokens per chunk

    Returns:
        List of chunk dicts with metadata:
        {
            'content': str,
            'post_slug': str,
            'post_title': str,
            'metadata': {...}
        }

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
    """Chunk a Document object into indexable chunks.

    MODERN (Phase 4): Works with Document abstraction instead of filesystem paths.

    Args:
        document: Content-addressed Document object
        max_tokens: Max tokens per chunk

    Returns:
        List of chunk dicts with metadata:
        {
            'content': str,
            'post_slug': str,
            'post_title': str,
            'metadata': {...},
            'document_id': str,
        }

    """
    # Extract slug and title from metadata
    metadata = document.metadata
    slug = metadata.get("slug", document.document_id[:8])
    title = metadata.get("title", slug.replace("-", " ").title())

    # Chunk the document content
    text_chunks = chunk_markdown(document.content, max_tokens=max_tokens)

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
