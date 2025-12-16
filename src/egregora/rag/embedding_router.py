"""Simplified embedding router using tenacity and batch endpoint.

Replaces complex threading/queuing with direct batch API calls and tenacity retries.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Annotated, Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from egregora.config import EMBEDDING_DIM
from egregora.models.model_cycler import GeminiKeyRotator, get_api_keys
from egregora.utils.env import get_google_api_key

logger = logging.getLogger(__name__)

# Constants
GENAI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_BATCH_SIZE = 100
HTTP_TOO_MANY_REQUESTS = 429


class EmbeddingError(Exception):
    """Exception raised for embedding API errors."""


class EmbeddingRouter:
    """Simplified embedding router that always uses the batch endpoint."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        max_batch_size: int = MAX_BATCH_SIZE,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.max_batch_size = max_batch_size
        self.timeout = timeout

        # Initialize key rotation
        initial_key = api_key or get_google_api_key()
        if not initial_key:
            # Fallback to key rotator loading from env if no key provided
            self.key_rotator = GeminiKeyRotator()
        else:
            # Seed rotator with provided key + environment keys
            # This ensures if the provided key fails, we have backups if available
            env_keys = get_api_keys()
            keys = [initial_key]
            if env_keys:
                keys.extend([k for k in env_keys if k != initial_key])
            self.key_rotator = GeminiKeyRotator(api_keys=keys)

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _call_batch_api(self, texts: list[str], task_type: str) -> list[list[float]]:
        """Call Gemini batch embedding API with retries and key rotation."""
        if not texts:
            return []

        url = f"{GENAI_API_BASE}/{self.model}:batchEmbedContents"

        requests_payload = [
            {
                "model": self.model,
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": EMBEDDING_DIM,
                "taskType": task_type,
            }
            for text in texts
        ]

        payload = {"requests": requests_payload}

        try:
            current_key = self.key_rotator.current_key

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, params={"key": current_key}, json=payload)
                response.raise_for_status()
                data = response.json()

                embeddings_data = data.get("embeddings", [])
                if not embeddings_data:
                    msg = f"No embeddings in response: {data}"
                    raise EmbeddingError(msg)

                result = []
                for i, emb_result in enumerate(embeddings_data):
                    values = emb_result.get("values")
                    if not values:
                        logger.warning("No values for embedding %d", i)
                        msg = f"No values for embedding {i}"
                        raise EmbeddingError(msg)
                    result.append(list(values))

                # Success - return results (don't reset key, stay on working key)
                return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTP_TOO_MANY_REQUESTS:
                logger.warning("Rate limit hit (429) on key %s...", current_key[:8])
                # Rotate key immediately
                next_key = self.key_rotator.next_key()
                if next_key:
                    logger.info("Rotated to next API key: %s...", next_key[:8])
                else:
                    logger.exception("All API keys exhausted.")
            # Re-raise so tenacity can retry (with new key if rotated, or backoff if exhausted)
            raise

    def embed(
        self,
        texts: Annotated[Sequence[str], "Texts to embed"],
        task_type: Annotated[str, "Task type"],
    ) -> list[list[float]]:
        """Embed texts using batch endpoint.

        Handles batching if texts > max_batch_size.
        """
        texts_list = list(texts)
        if not texts_list:
            return []

        all_embeddings = []

        # Process in chunks of max_batch_size
        for i in range(0, len(texts_list), self.max_batch_size):
            batch = texts_list[i : i + self.max_batch_size]
            embeddings = self._call_batch_api(batch, task_type)
            all_embeddings.extend(embeddings)

        return all_embeddings


# Global singleton and compatibility shim
_router: EmbeddingRouter | None = None
EndpointType = Any  # Deprecated
TaskType = str  # Deprecated


def create_embedding_router(
    *,
    model: str,
    api_key: str | None = None,
    max_batch_size: int = MAX_BATCH_SIZE,
    timeout: float = 60.0,
) -> EmbeddingRouter:
    return EmbeddingRouter(
        model=model, api_key=api_key, max_batch_size=max_batch_size, timeout=timeout
    )


def get_router(
    *,
    model: str,
    api_key: str | None = None,
    max_batch_size: int = MAX_BATCH_SIZE,
    timeout: float = 60.0,
) -> EmbeddingRouter:
    global _router  # noqa: PLW0603
    if _router is None:
        _router = create_embedding_router(
            model=model, api_key=api_key, max_batch_size=max_batch_size, timeout=timeout
        )
    return _router


get_embedding_router = get_router


def shutdown_router() -> None:
    pass  # No background workers to stop


def validate_api_key(api_key: str | None = None, *, model: str = "models/gemini-1.5-flash") -> None:
    """Validate API key (kept for compatibility)."""
    effective_key = api_key or get_google_api_key()
    if not effective_key:
        msg = "No API key provided"
        raise ValueError(msg)

    url = f"{GENAI_API_BASE}/{model}:countTokens"
    payload = {"contents": [{"parts": [{"text": "test"}]}]}

    with httpx.Client(timeout=10.0) as client:
        try:
            resp = client.post(url, params={"key": effective_key}, json=payload)
            resp.raise_for_status()
        except Exception as e:
            msg = f"API key validation failed: {e}"
            raise EmbeddingError(msg) from e


__all__ = [
    "EmbeddingError",
    "EmbeddingRouter",
    "create_embedding_router",
    "get_embedding_router",
    "get_router",
    "shutdown_router",
    "validate_api_key",
]
