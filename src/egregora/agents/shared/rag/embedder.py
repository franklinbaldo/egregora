"""Embedding generation using Google Generative AI HTTP API.

All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Annotated, Any

import httpx

from egregora.config import EMBEDDING_DIM

logger = logging.getLogger(__name__)

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
                    # Use 25% of the suggested delay (more aggressive)
                    return max(5.0, float(match.group(1)) * 0.25)
    except (KeyError, ValueError, AttributeError, TypeError):
        logger.debug("Could not parse retry delay")
    return 10.0  # Reduced from 60s to 10s


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


def embed_batch(
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
    embeddings = embed_batch(chunks, model=model, task_type=task_type)
    logger.info("Embedded %d chunks (%d dimensions)", len(embeddings), EMBEDDING_DIM)
    return embeddings


def embed_query(
    query_text: Annotated[str, "The query text to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
) -> Annotated[list[float], "The 768-dimensional embedding vector for the query"]:
    """Embed a single query string for retrieval.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
    """
    return embed_text(query_text, model=model, task_type="RETRIEVAL_QUERY")
