"""Simple helpers for embeddings using Google Generative AI HTTP API.

This module provides straightforward functions for embeddings operations using
direct HTTP API calls (no SDK dependency).

These are utility functions, not agents - they don't need the full pydantic-ai
agent infrastructure since they're simple vector calculations.

For content generation and enrichment, use pydantic-ai agents instead.

All embeddings use a fixed 768-dimension output for consistency and HNSW optimization.
"""

from __future__ import annotations
import logging
import os
from typing import Annotated, Any
import httpx
from egregora.config import EMBEDDING_DIM, from_pydantic_ai_model

logger = logging.getLogger(__name__)
GENAI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT = 60.0


def _get_api_key() -> str:
    """Get Google API key from environment.

    Returns:
        API key string

    Raises:
        ValueError: If GOOGLE_API_KEY is not set

    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY environment variable is required for embeddings. Set it before calling embedding functions."
        raise ValueError(msg)
    return api_key


def _call_with_retries(func: Any, *args: Any, max_retries: int = 3, **kwargs: Any) -> Any:
    """Simple retry wrapper for HTTP calls.

    Args:
        func: Function to call
        *args: Positional arguments
        max_retries: Maximum number of retries
        **kwargs: Keyword arguments

    Returns:
        Function result

    Raises:
        Exception: If all retries fail

    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning("Attempt %s/%s failed: %s. Retrying...", attempt + 1, max_retries, e)
            continue
    msg = f"All {max_retries} attempts failed"
    raise RuntimeError(msg) from last_error


def embed_text(
    text: Annotated[str, "The text to embed"],
    *,
    model: Annotated[str, "The embedding model to use (pydantic-ai format)"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    api_key: Annotated[str | None, "Optional API key (reads from GOOGLE_API_KEY if not provided)"] = None,
    timeout: Annotated[float, "Request timeout in seconds"] = DEFAULT_TIMEOUT,
) -> Annotated[list[float], "The embedding vector (768 dimensions)"]:
    """Embed a single text using the Google Generative AI HTTP API.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.

    Args:
        text: Text to embed
        model: Embedding model name in pydantic-ai format (e.g., "google-gla:text-embedding-004")
        task_type: Optional task type (e.g., "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY")
        api_key: Optional API key (reads from GOOGLE_API_KEY env var if not provided)
        timeout: Request timeout in seconds

    Returns:
        List of 768 floats representing the embedding vector

    Raises:
        RuntimeError: If embedding fails
        ValueError: If GOOGLE_API_KEY is not available

    """
    effective_api_key = api_key or _get_api_key()
    google_model = from_pydantic_ai_model(model)
    payload: dict[str, Any] = {
        "model": google_model,
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": EMBEDDING_DIM,
    }
    if task_type:
        payload["taskType"] = task_type
    url = f"{GENAI_API_BASE}/{google_model}:embedContent"
    try:

        def _make_request() -> list[float]:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, params={"key": effective_api_key}, json=payload)
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")
                if not embedding:
                    msg = f"No embedding in response: {data}"
                    raise RuntimeError(msg)
                values = embedding.get("values")
                if not values:
                    msg = f"No values in embedding: {embedding}"
                    raise RuntimeError(msg)
                return list(values)

        return _call_with_retries(_make_request)
    except Exception as e:
        logger.error("Failed to embed text: %s", e, exc_info=True)
        msg = f"Embedding failed: {e}"
        raise RuntimeError(msg) from e


def embed_batch(
    texts: Annotated[list[str], "List of texts to embed"],
    *,
    model: Annotated[str, "The embedding model to use (pydantic-ai format)"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    api_key: Annotated[str | None, "Optional API key (reads from GOOGLE_API_KEY if not provided)"] = None,
    timeout: Annotated[float, "Request timeout in seconds"] = DEFAULT_TIMEOUT,
) -> Annotated[list[list[float]], "List of embedding vectors (768 dimensions each)"]:
    """Embed multiple texts using the Google Generative AI batch HTTP API.

    This uses the batchEmbedContents API for efficient parallel processing.
    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.

    Args:
        texts: List of texts to embed
        model: Embedding model name in pydantic-ai format (e.g., "google-gla:text-embedding-004")
        task_type: Optional task type
        api_key: Optional API key (reads from GOOGLE_API_KEY env var if not provided)
        timeout: Request timeout in seconds

    Returns:
        List of 768-dimensional embedding vectors

    Raises:
        RuntimeError: If any embedding fails
        ValueError: If GOOGLE_API_KEY is not available

    """
    if not texts:
        return []
    logger.info("[blue]📚 Embedding model:[/] %s — %d text(s)", model, len(texts))
    effective_api_key = api_key or _get_api_key()
    google_model = from_pydantic_ai_model(model)
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
    try:

        def _make_request() -> list[list[float]]:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, params={"key": effective_api_key}, json=payload)
                response.raise_for_status()
                data = response.json()
                embeddings_data = data.get("embeddings", [])
                if not embeddings_data:
                    msg = f"No embeddings in response: {data}"
                    raise RuntimeError(msg)
                embeddings: list[list[float]] = []
                for i, embedding_result in enumerate(embeddings_data):
                    values = embedding_result.get("values")
                    if values is None:
                        logger.error("No embedding returned for text %d/%d", i + 1, len(texts))
                        msg = f"No embedding returned for text {i}: {texts[i][:50]}..."
                        raise RuntimeError(msg)
                    embeddings.append(list(values))
                logger.info("Embedded %d text(s)", len(embeddings))
                return embeddings

        return _call_with_retries(_make_request)
    except Exception as e:
        logger.error("Failed to batch embed texts: %s", e, exc_info=True)
        msg = f"Batch embedding failed: {e}"
        raise RuntimeError(msg) from e
