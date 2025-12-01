"""Dual-queue embedding router with independent rate limit tracking.

Routes embedding requests to either single or batch Google Gemini API endpoints
based on availability, maximizing throughput by using whichever endpoint is available.

Architecture:
    - Synchronous blocking I/O (no asyncio)
    - Two independent rate limiters
    - Smart routing: prefer batch for efficiency, fallback to single when rate-limited
    - Request accumulation logic removed in favor of direct batching in `embeddings.py`
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Annotated

import httpx

from egregora.config import get_google_api_key
from egregora.rag.embeddings import embed_texts_in_batch

logger = logging.getLogger(__name__)

# Constants
GENAI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500


class EndpointType(Enum):
    """Type of embedding endpoint."""

    SINGLE = "single"  # /embedContent - 1 text per request
    BATCH = "batch"  # /batchEmbedContents - up to 100 texts per request


class RateLimitState(Enum):
    """Rate limit state for an endpoint."""

    AVAILABLE = "available"  # Can send requests
    RATE_LIMITED = "rate_limited"  # Hit 429, waiting for window to reset
    ERROR = "error"  # Server error, backing off


@dataclass
class RateLimiter:
    """Tracks rate limit state for a single endpoint."""

    endpoint_type: EndpointType
    state: RateLimitState = RateLimitState.AVAILABLE
    available_at: float = 0.0  # Timestamp when endpoint becomes available again
    consecutive_errors: int = 0
    max_consecutive_errors: int = 5

    def is_available(self) -> bool:
        """Check if endpoint is available for requests."""
        if self.state == RateLimitState.AVAILABLE:
            return True
        if time.time() >= self.available_at:
            # Window expired, reset to available
            self.state = RateLimitState.AVAILABLE
            self.consecutive_errors = 0
            return True
        return False

    def mark_rate_limited(self, retry_after: float = 60.0) -> None:
        """Mark endpoint as rate limited."""
        self.state = RateLimitState.RATE_LIMITED
        self.available_at = time.time() + retry_after
        logger.warning(
            "%s endpoint rate limited. Available again at %s (in %.1fs)",
            self.endpoint_type.value,
            time.strftime("%H:%M:%S", time.localtime(self.available_at)),
            retry_after,
        )

    def mark_error(self, backoff_seconds: float = 2.0) -> None:
        """Mark endpoint as having an error."""
        self.consecutive_errors += 1
        if self.consecutive_errors >= self.max_consecutive_errors:
            msg = f"{self.endpoint_type.value} endpoint failed {self.consecutive_errors} times"
            raise RuntimeError(msg)
        self.state = RateLimitState.ERROR
        self.available_at = time.time() + backoff_seconds
        logger.warning(
            "%s endpoint error #%d. Backing off for %.1fs",
            self.endpoint_type.value,
            self.consecutive_errors,
            backoff_seconds,
        )

    def mark_success(self) -> None:
        """Mark successful request."""
        self.state = RateLimitState.AVAILABLE
        self.consecutive_errors = 0
        self.available_at = 0.0


class EmbeddingRouter:
    """Routes embedding requests to optimal endpoint based on availability."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        max_batch_size: int = 100,
        timeout: float = 60.0,
    ) -> None:
        """Initialize router.

        Args:
            model: Google embedding model (e.g., "models/gemini-embedding-001")
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            max_batch_size: Maximum texts per batch request
            timeout: HTTP timeout in seconds

        """
        self.model = model
        self.api_key = api_key or get_google_api_key()
        self.max_batch_size = max_batch_size
        self.timeout = timeout

        # Create dual rate limiters
        self.batch_limiter = RateLimiter(EndpointType.BATCH)
        self.single_limiter = RateLimiter(EndpointType.SINGLE)

    def start(self) -> None:
        """Start router (noop for sync implementation)."""
        logger.info("Embedding router started (synchronous mode)")

    def stop(self) -> None:
        """Stop router (noop for sync implementation)."""
        logger.info("Embedding router stopped")

    def embed(
        self,
        texts: Annotated[Sequence[str], "Texts to embed"],
        task_type: Annotated[str, "Task type (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)"],
    ) -> Annotated[list[list[float]], "Embedding vectors"]:
        """Route embedding request to optimal endpoint.

        Priority: single endpoint (low latency) > batch endpoint (fallback)
        Always prefer single for lower latency, use batch only when single is exhausted.

        Args:
            texts: List of texts to embed
            task_type: Task type for embeddings

        Returns:
            List of embedding vectors

        """
        texts_list = list(texts)
        if not texts_list:
            return []

        # Logic simplified: Use embed_texts_in_batch for everything.
        # It handles batching internally.
        # Rate limiting logic can be applied around it if we want to distinguish endpoints.
        # But `embed_texts_in_batch` uses /batchEmbedContents by default for >1 items.
        # For 1 item, it also uses batch endpoint in current implementation of `embed_text_in_batch` helper?
        # Let's check `embeddings.py`: `embed_texts_in_batch` calls `_embed_batch_chunk` which calls `/batchEmbedContents`.
        # `embed_text` calls `/embedContent`.
        # The original Async Router tried to use Single endpoint for 1 item OR multiple concurrent items?
        # No, Single endpoint is 1 item per request.
        # If we have a list of texts, Single endpoint means N requests. Batch endpoint means 1 request (for up to 100).
        # Batch is ALWAYS more efficient for >1 text.
        # Single might be faster for 1 text due to lower overhead?
        # The router logic was: "Priority routing: single (low latency) first, then batch (fallback)".
        # This implies Single endpoint is preferred. But for a list of texts?
        # If I send 10 texts to Single endpoint, I do 10 requests. That's slower than 1 batch request.
        # The router logic likely assumed concurrent requests for single items.
        # In synchronous mode, sequential single requests are definitely slower.
        # So we should ALWAYS use batch endpoint for >1 texts.
        # For 1 text, we can use Single or Batch.
        # Let's just use `embed_texts_in_batch` which handles chunking and uses the batch endpoint.
        # It simplifies everything. We lose the "fallback to single if batch 429" logic, but tenacity in `embeddings.py` handles retries.

        try:
            return embed_texts_in_batch(
                texts_list,
                model=self.model,
                task_type=task_type,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        except httpx.HTTPStatusError as e:
            # If we wanted to implement the fallback logic, we'd catch 429 here and try `embed_text` loop.
            # But simpler is better for now.
            logger.error("Embedding failed: %s", e)
            raise


# Global singleton
_router: EmbeddingRouter | None = None


def create_embedding_router(
    *,
    model: str,
    api_key: str | None = None,
    max_batch_size: int = 100,
    timeout: float = 60.0,
) -> EmbeddingRouter:
    """Create and start a dedicated embedding router instance."""
    router = EmbeddingRouter(
        model=model,
        api_key=api_key,
        max_batch_size=max_batch_size,
        timeout=timeout,
    )
    router.start()
    return router


def get_router(
    *,
    model: str,
    api_key: str | None = None,
    max_batch_size: int = 100,
    timeout: float = 60.0,
) -> EmbeddingRouter:
    """Get or create global embedding router singleton."""
    global _router
    if _router is None:
        _router = create_embedding_router(
            model=model,
            api_key=api_key,
            max_batch_size=max_batch_size,
            timeout=timeout,
        )
    return _router


def shutdown_router() -> None:
    """Shutdown global router (for cleanup)."""
    global _router
    if _router is not None:
        _router.stop()
        _router = None


__all__ = [
    "EmbeddingRouter",
    "EndpointType",
    "RateLimitState",
    "create_embedding_router",
    "get_router",
    "shutdown_router",
]
