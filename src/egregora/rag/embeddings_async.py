"""Async embedding API using dual-queue router for optimal throughput.

This module provides async embedding functions that route requests
to either single or batch Google Gemini API endpoints based on availability,
maximizing throughput by using whichever endpoint has capacity.

Key features:
- Dual-queue routing (single + batch endpoints)
- Independent rate limit tracking per endpoint
- Low-latency priority (prefers single endpoint)
- Request accumulation during rate limits
- Configurable via RAGSettings
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Annotated

from egregora.config import get_google_api_key
from egregora.config.settings import load_config
from egregora.rag.embedding_router import get_router

logger = logging.getLogger(__name__)


async def embed_texts_async(
    texts: Annotated[Sequence[str], "Texts to embed"],
    *,
    task_type: Annotated[str, "Task type (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)"],
    api_key: Annotated[str | None, "Optional API key (defaults to GOOGLE_API_KEY env var)"] = None,
) -> Annotated[list[list[float]], "Embedding vectors (768 dimensions each)"]:
    """Embed texts using dual-queue router for optimal throughput.

    Routes requests to single or batch endpoint based on availability and latency needs.
    Priority: single endpoint (low latency) > batch endpoint (fallback).

    Args:
        texts: Sequence of texts to embed
        task_type: Task type for embeddings (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)
        api_key: Optional API key (defaults to GOOGLE_API_KEY env var)

    Returns:
        List of 768-dimensional embedding vectors

    Raises:
        ValueError: If GOOGLE_API_KEY not set and api_key not provided
        RuntimeError: If embedding API fails after retries
        httpx.HTTPError: If API request fails

    """
    if not texts:
        return []

    # Load config for router settings
    config = load_config()
    rag_settings = config.rag

    # Get or create router
    router = await get_router(
        api_key=api_key,
        max_batch_size=rag_settings.embedding_max_batch_size,
        timeout=rag_settings.embedding_timeout,
    )

    # Route to optimal endpoint
    logger.info("Embedding %d text(s) with task_type=%s", len(texts), task_type)
    embeddings = await router.embed(texts, task_type)
    logger.info("Embedded %d text(s) successfully", len(embeddings))

    return embeddings


async def embed_chunks_async(
    chunks: Annotated[list[str], "Text chunks to embed"],
    *,
    task_type: Annotated[str, "Task type for embeddings"] = "RETRIEVAL_DOCUMENT",
) -> Annotated[list[list[float]], "Embedding vectors for chunks"]:
    """Embed text chunks for indexing.

    Convenience wrapper around embed_texts_async with default task_type.

    Args:
        chunks: List of text chunks to embed
        task_type: Task type (default: RETRIEVAL_DOCUMENT)

    Returns:
        List of 768-dimensional embedding vectors

    """
    if not chunks:
        return []
    return await embed_texts_async(chunks, task_type=task_type)


async def embed_query_async(
    query_text: Annotated[str, "Query text to embed"],
) -> Annotated[list[float], "Embedding vector for query"]:
    """Embed a single query string for retrieval.

    Uses RETRIEVAL_QUERY task type for optimal query embeddings.
    Routes to single endpoint for lowest latency.

    Args:
        query_text: Query text to embed

    Returns:
        768-dimensional embedding vector

    """
    results = await embed_texts_async([query_text], task_type="RETRIEVAL_QUERY")
    return results[0]


def is_rag_available() -> bool:
    """Check if RAG functionality is available (API key present).

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    """
    try:
        get_google_api_key()
        return True
    except ValueError:
        return False


__all__ = [
    "embed_texts_async",
    "embed_chunks_async",
    "embed_query_async",
    "is_rag_available",
]
