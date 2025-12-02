"""Embedding generation for RAG knowledge system.

Handles text embedding via Google Generative AI API with retry logic
and batch processing support.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

import os
from egregora.config import EMBEDDING_DIM

logger = logging.getLogger(__name__)



# Constants
GENAI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_BATCH_SIZE = 100  # Google API limit for batchEmbedContents
HTTP_TOO_MANY_REQUESTS = 429  # Rate limit status code
HTTP_SERVER_ERROR = 500  # Server error status code threshold


def _get_timeout() -> float:
    """Get request timeout from config or default."""
    # This could be exposed in config if needed, defaulting to 60s
    return 60.0


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
def _call_with_retries(func: Any) -> Any:
    """Retry wrapper for HTTP calls with tenacity."""
    try:
        return func()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == HTTP_TOO_MANY_REQUESTS:
            # Parse retry-after if available, but tenacity handles backoff
            logger.warning("Rate limit exceeded (429). Retrying...")
        elif e.response.status_code >= HTTP_SERVER_ERROR:
            logger.warning("Server error %s. Retrying...", e.response.status_code)
        else:
            # Don't retry client errors (4xx) except 429
            raise
        raise


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
    timeout: Annotated[float | None, "Request timeout in seconds"] = None,
) -> Annotated[list[float], "The embedding vector (768 dimensions)"]:
    """Embed a single text using the Google Generative AI HTTP API.

    Args:
        text: Text to embed
        model: Embedding model name (e.g., 'models/text-embedding-004')
        task_type: Optional task type hint for the embedding
        api_key: Optional API key (defaults to GOOGLE_API_KEY env var)
        timeout: Request timeout in seconds

    Returns:
        768-dimensional embedding vector

    Raises:
        ValueError: If GOOGLE_API_KEY not set and api_key not provided
        RuntimeError: If embedding API returns invalid response
        httpx.HTTPError: If API request fails after retries

    """
    effective_api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not effective_api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY required")

    effective_timeout = timeout or _get_timeout()
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
        with httpx.Client(timeout=effective_timeout) as client:
            response = client.post(url, params={"key": effective_api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
            embedding = _validate_embedding_response(data)
            return list(embedding["values"])

    return _call_with_retries(_make_request)


def _embed_batch_chunk(
    texts: Annotated[list[str], "List of texts to embed (max 100)"],
    *,
    model: Annotated[str, "The embedding model to use"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    api_key: Annotated[str | None, "Optional API key"] = None,
    timeout: Annotated[float | None, "Request timeout in seconds"] = None,
) -> Annotated[list[list[float]], "List of embedding vectors"]:
    """Embed a single batch chunk (internal helper).

    Args:
        texts: List of texts to embed (should be ≤100 items)
        model: Embedding model name
        task_type: Optional task type hint
        api_key: Optional API key
        timeout: Request timeout in seconds

    Returns:
        List of 768-dimensional embedding vectors

    Raises:
        ValueError: If GOOGLE_API_KEY not set and api_key not provided
        RuntimeError: If embedding API returns invalid response
        httpx.HTTPError: If API request fails after retries

    """
    effective_api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not effective_api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY required")

    effective_timeout = timeout or _get_timeout()
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
        with httpx.Client(timeout=effective_timeout) as client:
            response = client.post(url, params={"key": effective_api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
            embeddings_data = _validate_batch_response(data)
            embeddings: list[list[float]] = []
            for i, embedding_result in enumerate(embeddings_data):
                values = embedding_result.get("values")
                _validate_embedding_values(values, i, texts[i])
                embeddings.append(list(values))
            return embeddings

    return _call_with_retries(_make_request)


def embed_texts_in_batch(
    texts: Annotated[list[str], "List of texts to embed"],
    *,
    model: Annotated[str, "The embedding model to use (Google format, e.g., 'models/text-embedding-004')"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    api_key: Annotated[str | None, "Optional API key (reads from GOOGLE_API_KEY if not provided)"] = None,
    timeout: Annotated[float | None, "Request timeout in seconds"] = None,
) -> Annotated[list[list[float]], "List of embedding vectors (768 dimensions each)"]:
    """Embed multiple texts using the Google Generative AI batch HTTP API.

    Automatically handles the Google API limit of 100 items per batch by chunking
    larger requests into multiple API calls.

    Args:
        texts: List of texts to embed
        model: Embedding model name (e.g., 'models/text-embedding-004')
        task_type: Optional task type hint for the embeddings
        api_key: Optional API key (defaults to GOOGLE_API_KEY env var)
        timeout: Request timeout in seconds

    Returns:
        List of 768-dimensional embedding vectors

    Raises:
        ValueError: If GOOGLE_API_KEY not set and api_key not provided
        RuntimeError: If embedding API returns invalid response
        httpx.HTTPError: If API request fails after retries

    """
    if not texts:
        return []

    # Fast path: single batch
    if len(texts) <= MAX_BATCH_SIZE:
        logger.info("Embedding %d text(s) with model %s", len(texts), model)
        return _embed_batch_chunk(texts, model=model, task_type=task_type, api_key=api_key, timeout=timeout)

    # Chunked path: multiple batches for large inputs
    logger.info(
        "Embedding %d text(s) in batches of %d with model %s",
        len(texts),
        MAX_BATCH_SIZE,
        model,
    )
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        chunk = texts[i : i + MAX_BATCH_SIZE]
        logger.debug(
            "Processing batch %d/%d", i // MAX_BATCH_SIZE + 1, (len(texts) - 1) // MAX_BATCH_SIZE + 1
        )
        embeddings = _embed_batch_chunk(
            chunk, model=model, task_type=task_type, api_key=api_key, timeout=timeout
        )
        all_embeddings.extend(embeddings)

    logger.info("Embedded %d text(s) total", len(all_embeddings))
    return all_embeddings


def embed_chunks(
    chunks: Annotated[list[str], "A list of text chunks to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    task_type: Annotated[str, "The task type for the embedding model"] = "RETRIEVAL_DOCUMENT",
) -> Annotated[list[list[float]], "A list of 768-dimensional embedding vectors for the chunks"]:
    """Embed text chunks using the Google Generative AI HTTP API.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.

    Args:
        chunks: List of text chunks to embed
        model: Embedding model name
        task_type: Task type for embeddings (default: RETRIEVAL_DOCUMENT)

    Returns:
        List of 768-dimensional embedding vectors

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

    Uses batch API even for single queries to benefit from better rate limiting.

    Args:
        query_text: Query text to embed
        model: Embedding model name

    Returns:
        768-dimensional embedding vector

    """
    # Use batch API with single item for better rate limits
    results = embed_texts_in_batch([query_text], model=model, task_type="RETRIEVAL_QUERY")
    return results[0]


def is_rag_available() -> bool:
    """Check if RAG functionality is available (API key present).

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    """
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


__all__ = [
    "embed_chunks",
    "embed_query_text",
    "embed_text",
    "embed_texts_in_batch",
    "is_rag_available",
]
