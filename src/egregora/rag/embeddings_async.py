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
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Annotated

from egregora.config import get_google_api_key
from egregora.config.settings import EgregoraConfig, load_egregora_config
from egregora.rag.embedding_router import EmbeddingRouter, get_router

logger = logging.getLogger(__name__)


async def embed_texts_async(
    texts: Annotated[Sequence[str], "Texts to embed"],
    *,
    task_type: Annotated[str, "Task type (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)"],
    api_key: Annotated[str | None, "Optional API key (defaults to GOOGLE_API_KEY env var)"] = None,
    router: EmbeddingRouter | None = None,
    router_factory: Callable[..., Awaitable[EmbeddingRouter]] | None = None,
) -> Annotated[list[list[float]], "Embedding vectors (768 dimensions each)"]:
    """Embed texts using dual-queue router for optimal throughput.

    Routes requests to single or batch endpoint based on availability and latency needs.
    Priority: single endpoint (low latency) > batch endpoint (fallback).

    Args:
        texts: Sequence of texts to embed
        task_type: Task type for embeddings (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)
        api_key: Optional API key (defaults to GOOGLE_API_KEY env var)
        router: Optional embedding router instance to use
        router_factory: Optional factory to construct a router when one isn't provided

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
    try:
        config = load_egregora_config(Path.cwd())
    except (OSError, ValueError):
        # Fall back to default config if not found
        config = EgregoraConfig()
    rag_settings = config.rag
    embedding_model = config.models.embedding

    router_factory = router_factory or get_router
    router_instance = router
    if router_instance is None:
        router_instance = await router_factory(
            model=embedding_model,
            api_key=api_key,
            max_batch_size=rag_settings.embedding_max_batch_size,
            timeout=rag_settings.embedding_timeout,
        )

    # Route to optimal endpoint
    logger.info("Embedding %d text(s) with task_type=%s", len(texts), task_type)
    embeddings = await router_instance.embed(texts, task_type)
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
    "embed_chunks_async",
    "embed_query_async",
    "embed_texts_async",
    "is_rag_available",
]
