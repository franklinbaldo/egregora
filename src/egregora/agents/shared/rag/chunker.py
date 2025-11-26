"""Text chunking logic for RAG knowledge system.

Splits documents into manageable chunks for embedding and retrieval.
Works with Document instances from the pipeline.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from egregora.utils.frontmatter_utils import parse_frontmatter
from egregora.utils.text import estimate_tokens

if TYPE_CHECKING:
    from egregora.data_primitives import Document

logger = logging.getLogger(__name__)

# Chunking constants
DEFAULT_MAX_TOKENS = 1800  # Default maximum tokens per chunk
DEFAULT_OVERLAP_TOKENS = 150  # Default overlap between chunks for context

# Regex patterns
POST_FILENAME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}-(.+)")
DATE_FILENAME_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def chunk_markdown(
    content: str, max_tokens: int = DEFAULT_MAX_TOKENS, overlap_tokens: int = DEFAULT_OVERLAP_TOKENS
) -> list[str]:
    r"""Chunk markdown content respecting token limits using LangChain.

    Args:
        content: Markdown text to chunk
        max_tokens: Maximum tokens per chunk (default: 1800)
        overlap_tokens: Tokens of overlap between chunks (default: 150)

    Returns:
        List of markdown text chunks

    """
    if not content.strip():
        return []

    # LangChain's text splitter is more robust for this task.
    # It handles markdown structure, sentence splitting, and token estimation.
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name="cl100k_base",  # Standard encoder for Gemini
        chunk_size=max_tokens,
        chunk_overlap=overlap_tokens,
        separators=[
            "\n\n",  # Split by paragraph first
            "\n",  # Then by line
            " ",  # Then by word
            "",  # Finally by character
        ],
    )
    return text_splitter.split_text(content)


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
        match = POST_FILENAME_PATTERN.match(filename)
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
        match = DATE_FILENAME_PATTERN.match(filename)
        if match:
            metadata["date"] = match.group(1)
        else:
            metadata["date"] = None

    return (metadata, body)


def chunk_document(post_path: Path, max_tokens: int = DEFAULT_MAX_TOKENS) -> list[dict[str, Any]]:
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


def chunk_from_document(document: Document, max_tokens: int = DEFAULT_MAX_TOKENS) -> list[dict[str, Any]]:
    """Chunk a Document object into indexable chunks.

    This is the primary chunking function for Document-based RAG indexing.
    Output adapters provide Documents, which are chunked for embedding.

    Args:
        document: Document instance to chunk
        max_tokens: Maximum tokens per chunk (default: 1800)

    Returns:
        List of chunk dicts with content, metadata, document_id, and indices

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
