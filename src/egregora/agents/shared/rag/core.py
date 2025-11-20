"""Core RAG primitives: chunking and embedding.

This module combines low-level chunking and embedding operations
that other RAG components build upon.

All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import httpx

from egregora.config import EMBEDDING_DIM
from egregora.utils.frontmatter_utils import parse_frontmatter

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document

logger = logging.getLogger(__name__)

# ============================================================================
# Chunking Functions
# ============================================================================


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: ~4 chars per token).

    Gemini embedding limit: 2048 tokens
    We use 1800 tokens max per chunk for safety.
    """
    # Centralized implementation
    from egregora.agents.model_limits import estimate_tokens as _estimate  # noqa: PLC0415

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
    content = post_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
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
    return (metadata, body)


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


# ============================================================================
# Embedding Functions
# ============================================================================

GENAI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT = 60.0
HTTP_TOO_MANY_REQUESTS = 429  # Rate limit exceeded status code


def _get_api_key() -> str:
    """Get Google API key from environment."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY environment variable is required"
        raise ValueError(msg)
    return api_key


def _parse_retry_delay(error_response: dict[str, Any]) -> float:
    """Parse retry delay from 429 error response."""
    try:
        details = error_response.get("error", {}).get("details", [])
        for detail in details:
            if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                retry_delay = detail.get("retryDelay", "10s")
                match = re.match(r"(\d+)s", retry_delay)
                if match:
                    # Use 100% of the suggested delay (respect server guidance)
                    return max(5.0, float(match.group(1)))
    except (KeyError, ValueError, AttributeError, TypeError):
        logger.debug("Could not parse retry delay")
    return 10.0


def _call_with_retries(func: Any, max_retries: int = 3) -> Any:
    """Retry wrapper for HTTP calls with rate limit handling."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == HTTP_TOO_MANY_REQUESTS:
                try:
                    error_data = e.response.json()
                    delay = _parse_retry_delay(error_data)
                    logger.warning(
                        "Rate limit exceeded (429). Waiting %s seconds before retry %s/%s...",
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(delay)
                    continue
                except (ValueError, KeyError, AttributeError):
                    logger.warning("429 error but could not parse response. Waiting 10s...")
                    time.sleep(10)
                    continue
            if attempt < max_retries - 1:
                logger.warning("Attempt %s/%s failed: %s. Retrying...", attempt + 1, max_retries, e)
                time.sleep(2)
            continue
        except httpx.HTTPError as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning("Attempt %s/%s failed: %s. Retrying...", attempt + 1, max_retries, e)
                time.sleep(2)
            continue
    msg = f"All {max_retries} attempts failed"
    raise RuntimeError(msg) from last_error


def _validate_embedding_response(data: dict[str, Any]) -> dict[str, Any]:
    """Validate embedding response."""
    embedding = data.get("embedding")
    if not embedding:
        msg = f"No embedding in response: {data}"
        raise RuntimeError(msg)
    return embedding


def _validate_batch_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate batch embedding response."""
    embeddings = data.get("embeddings")
    if not embeddings:
        msg = f"No embeddings in batch response: {data}"
        raise RuntimeError(msg)
    return embeddings


def _validate_embedding_values(values: Any, text_index: int, text: str) -> None:
    """Validate embedding vector values."""
    if not values:
        msg = f"No embedding returned for text {text_index}: {text[:50]}..."
        raise RuntimeError(msg)


def embed_text(
    text: Annotated[str, "The text to embed"],
    *,
    model: Annotated[str, "The embedding model to use (Google format, e.g., 'models/text-embedding-004')"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    api_key: Annotated[str | None, "Optional API key (reads from GOOGLE_API_KEY if not provided)"] = None,
    timeout: Annotated[float, "Request timeout in seconds"] = DEFAULT_TIMEOUT,
) -> Annotated[list[float], "The embedding vector (768 dimensions)"]:
    """Embed a single text using the Google Generative AI HTTP API."""
    effective_api_key = api_key or _get_api_key()
    google_model = model
    payload: dict[str, Any] = {
        "model": google_model,
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": EMBEDDING_DIM,
    }
    if task_type:
        payload["taskType"] = task_type
    url = f"{GENAI_API_BASE}/{google_model}:embedContent"

    def _make_request() -> list[float]:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, params={"key": effective_api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
            embedding = _validate_embedding_response(data)
            return list(embedding["values"])

    return _call_with_retries(_make_request)


def embed_texts_in_batch(
    texts: Annotated[list[str], "List of texts to embed"],
    *,
    model: Annotated[str, "The embedding model to use (Google format, e.g., 'models/text-embedding-004')"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    api_key: Annotated[str | None, "Optional API key (reads from GOOGLE_API_KEY if not provided)"] = None,
    timeout: Annotated[float, "Request timeout in seconds"] = DEFAULT_TIMEOUT,
) -> Annotated[list[list[float]], "List of embedding vectors (768 dimensions each)"]:
    """Embed multiple texts using the Google Generative AI batch HTTP API."""
    if not texts:
        return []
    logger.info("Embedding %d text(s) with model %s", len(texts), model)
    effective_api_key = api_key or _get_api_key()
    google_model = model
    requests = []
    for text in texts:
        request: dict[str, Any] = {
            "model": google_model,
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": EMBEDDING_DIM,
        }
        if task_type:
            request["taskType"] = task_type
        requests.append(request)
    payload = {"requests": requests}
    url = f"{GENAI_API_BASE}/{google_model}:batchEmbedContents"

    def _make_request() -> list[list[float]]:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, params={"key": effective_api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
            embeddings_data = _validate_batch_response(data)
            embeddings: list[list[float]] = []
            for i, embedding_result in enumerate(embeddings_data):
                values = embedding_result.get("values")
                _validate_embedding_values(values, i, texts[i])
                embeddings.append(list(values))
            logger.info("Embedded %d text(s)", len(embeddings))
            return embeddings

    return _call_with_retries(_make_request)


def embed_chunks(
    chunks: Annotated[list[str], "A list of text chunks to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    task_type: Annotated[str, "The task type for the embedding model"] = "RETRIEVAL_DOCUMENT",
) -> Annotated[list[list[float]], "A list of 768-dimensional embedding vectors for the chunks"]:
    """Embed text chunks using the Google Generative AI HTTP API.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
    """
    if not chunks:
        return []
    embeddings = embed_texts_in_batch(chunks, model=model, task_type=task_type)
    logger.info("Embedded %d chunks (%d dimensions)", len(embeddings), EMBEDDING_DIM)
    return embeddings


def embed_query_text(
    query_text: Annotated[str, "The query text to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
) -> Annotated[list[float], "The 768-dimensional embedding vector for the query"]:
    """Embed a single query string for retrieval.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
    """
    return embed_text(query_text, model=model, task_type="RETRIEVAL_QUERY")
