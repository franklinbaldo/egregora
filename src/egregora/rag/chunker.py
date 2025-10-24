"""Document chunking for RAG system."""

import logging
import re
from pathlib import Path
from typing import Any

import frontmatter

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count (rough approximation: ~4 chars per token).

    Gemini embedding limit: 2048 tokens
    We use 1800 tokens max per chunk for safety.
    """
    return len(text) // 4


def chunk_markdown(
    content: str,
    max_tokens: int = 1800,
    overlap_tokens: int = 150,
) -> list[str]:
    """
    Chunk markdown content respecting token limits.

    Strategy:
    - Split on paragraph boundaries (\\n\\n)
    - Max 1800 tokens per chunk (safe under 2048 limit)
    - 150 token overlap between chunks for context

    Args:
        content: Markdown text
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap between consecutive chunks

    Returns:
        List of text chunks
    """
    # Split into paragraphs
    paragraphs = content.split("\n\n")

    chunks = []
    current_chunk = []
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = estimate_tokens(para)

        # Check if adding this paragraph exceeds limit
        if current_tokens + para_tokens > max_tokens and current_chunk:
            # Save current chunk
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)

            # Start new chunk with overlap (keep last few paragraphs)
            overlap_paras = []
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

    # Add final chunk
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append(chunk_text)

    return chunks


def parse_post(post_path: Path) -> tuple[dict[str, Any], str]:
    """
    Parse blog post with YAML frontmatter.

    Returns:
        (metadata_dict, content_string)
    """
    with open(post_path, encoding="utf-8") as f:
        post = frontmatter.load(f)

    metadata = dict(post.metadata)

    # Extract slug from filename if not in metadata
    if "slug" not in metadata:
        # Filename format: YYYY-MM-DD-slug.md
        filename = post_path.stem
        match = re.match(r"\d{4}-\d{2}-\d{2}-(.+)", filename)
        if match:
            metadata["slug"] = match.group(1)
        else:
            metadata["slug"] = filename

    # Ensure required fields
    if "title" not in metadata:
        metadata["title"] = metadata["slug"].replace("-", " ").title()

    if "date" not in metadata:
        # Try to extract from filename
        filename = post_path.stem
        match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
        if match:
            metadata["date"] = match.group(1)
        else:
            metadata["date"] = None

    return metadata, post.content


def chunk_document(
    post_path: Path,
    max_tokens: int = 1800,
) -> list[dict[str, Any]]:
    """
    Chunk a blog post into indexable chunks.

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

    # Chunk content
    text_chunks = chunk_markdown(content, max_tokens=max_tokens)

    # Build chunk objects
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

    logger.info(f"Chunked {post_path.name} into {len(chunks)} chunks")

    return chunks
