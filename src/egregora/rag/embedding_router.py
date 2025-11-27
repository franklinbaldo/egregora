"""Dual-queue embedding router with independent rate limit tracking.

Routes embedding requests to either single or batch Google Gemini API endpoints
based on availability, maximizing throughput by using whichever endpoint is available.

Architecture:
    - Two independent queues (single + batch)
    - Two independent rate limiters
    - Smart routing: prefer batch for efficiency, fallback to single when rate-limited
    - Request accumulation during rate limit waits
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any

import httpx

from egregora.config import EMBEDDING_DIM, get_google_api_key

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


@dataclass
class EmbeddingRequest:
    """A pending embedding request."""

    texts: list[str]
    task_type: str
    future: asyncio.Future[list[list[float]]]
    submitted_at: float = field(default_factory=time.time)


@dataclass
class EndpointQueue:
    """Queue and worker for a single endpoint type."""

    endpoint_type: EndpointType
    rate_limiter: RateLimiter
    queue: asyncio.Queue[EmbeddingRequest] = field(default_factory=asyncio.Queue)
    worker_task: asyncio.Task[None] | None = None
    max_batch_size: int = 100
    api_key: str = field(default_factory=get_google_api_key)
    timeout: float = 60.0

    async def start(self) -> None:
        """Start background worker."""
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("Started %s endpoint worker", self.endpoint_type.value)

    async def stop(self) -> None:
        """Stop background worker."""
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped %s endpoint worker", self.endpoint_type.value)

    async def submit(self, texts: list[str], task_type: str) -> list[list[float]]:
        """Submit request and wait for result."""
        future: asyncio.Future[list[list[float]]] = asyncio.Future()
        request = EmbeddingRequest(texts, task_type, future)
        await self.queue.put(request)
        return await future

    def is_available(self) -> bool:
        """Check if endpoint is available."""
        return self.rate_limiter.is_available()

    async def _worker(self) -> None:
        """Background worker that processes queue."""
        while True:
            try:
                # Wait for first request
                first_request = await self.queue.get()

                # Accumulate more requests if available (non-blocking)
                requests = [first_request]
                total_texts = len(first_request.texts)

                # For batch endpoint, accumulate up to max_batch_size
                if self.endpoint_type == EndpointType.BATCH:
                    while total_texts < self.max_batch_size:
                        try:
                            req = self.queue.get_nowait()
                            if total_texts + len(req.texts) <= self.max_batch_size:
                                requests.append(req)
                                total_texts += len(req.texts)
                            else:
                                # Would exceed batch size, put it back
                                await self.queue.put(req)
                                break
                        except asyncio.QueueEmpty:
                            break

                # Wait if rate limited
                while not self.rate_limiter.is_available():
                    wait_time = max(0.1, self.rate_limiter.available_at - time.time())
                    logger.debug(
                        "%s endpoint waiting %.1fs for rate limit window", self.endpoint_type.value, wait_time
                    )
                    await asyncio.sleep(min(wait_time, 1.0))

                # Process accumulated requests
                await self._process_batch(requests)

            except asyncio.CancelledError:
                # Worker cancelled, propagate to pending requests
                pending_requests = [first_request] if "first_request" in locals() else []
                while not self.queue.empty():
                    try:
                        pending_requests.append(self.queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                for req in pending_requests:
                    if not req.future.done():
                        req.future.cancel()
                raise
            except Exception:
                logger.exception("Unexpected error in %s worker", self.endpoint_type.value)
                await asyncio.sleep(1.0)  # Brief pause before continuing

    async def _process_batch(self, requests: list[EmbeddingRequest]) -> None:
        """Process a batch of accumulated requests."""
        if not requests:
            return

        # Group by task_type for efficiency
        by_task_type: dict[str, list[EmbeddingRequest]] = {}
        for req in requests:
            by_task_type.setdefault(req.task_type, []).append(req)

        # Process each task_type group
        for task_type, group_requests in by_task_type.items():
            all_texts = []
            for req in group_requests:
                all_texts.extend(req.texts)

            try:
                # Call appropriate API endpoint
                if self.endpoint_type == EndpointType.SINGLE:
                    embeddings = await self._call_single_endpoint(all_texts, task_type)
                else:
                    embeddings = await self._call_batch_endpoint(all_texts, task_type)

                # Mark success
                self.rate_limiter.mark_success()

                # Distribute results to callers
                offset = 0
                for req in group_requests:
                    count = len(req.texts)
                    req.future.set_result(embeddings[offset : offset + count])
                    offset += count

            except Exception as e:
                # Propagate error to all waiting futures
                for req in group_requests:
                    if not req.future.done():
                        req.future.set_exception(e)

    async def _call_single_endpoint(self, texts: list[str], task_type: str) -> list[list[float]]:
        """Call /embedContent for each text."""
        embeddings = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for text in texts:
                payload: dict[str, Any] = {
                    "model": "models/text-embedding-004",  # TODO: Make configurable
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": EMBEDDING_DIM,
                    "taskType": task_type,
                }
                url = f"{GENAI_API_BASE}/models/text-embedding-004:embedContent"

                try:
                    response = await client.post(url, params={"key": self.api_key}, json=payload)
                    self._handle_response_status(response)
                    data = response.json()
                    embedding = data.get("embedding", {}).get("values")
                    if not embedding:
                        msg = f"No embedding in response: {data}"
                        raise RuntimeError(msg)
                    embeddings.append(list(embedding))

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == HTTP_TOO_MANY_REQUESTS:
                        retry_after = float(e.response.headers.get("Retry-After", 60))
                        self.rate_limiter.mark_rate_limited(retry_after)
                        raise
                    if e.response.status_code >= HTTP_SERVER_ERROR:
                        self.rate_limiter.mark_error()
                        raise
                    raise  # Client error, don't retry

        return embeddings

    async def _call_batch_endpoint(self, texts: list[str], task_type: str) -> list[list[float]]:
        """Call /batchEmbedContents for multiple texts."""
        requests_payload = []
        for text in texts:
            req: dict[str, Any] = {
                "model": "models/text-embedding-004",  # TODO: Make configurable
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": EMBEDDING_DIM,
                "taskType": task_type,
            }
            requests_payload.append(req)

        payload = {"requests": requests_payload}
        url = f"{GENAI_API_BASE}/models/text-embedding-004:batchEmbedContents"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, params={"key": self.api_key}, json=payload)
                self._handle_response_status(response)
                data = response.json()
                embeddings_data = data.get("embeddings", [])
                if not embeddings_data:
                    msg = f"No embeddings in batch response: {data}"
                    raise RuntimeError(msg)

                embeddings = []
                for i, emb_result in enumerate(embeddings_data):
                    values = emb_result.get("values")
                    if not values:
                        msg = f"No embedding for text {i}: {texts[i][:50]}..."
                        raise RuntimeError(msg)
                    embeddings.append(list(values))

                return embeddings

            except httpx.HTTPStatusError as e:
                if e.response.status_code == HTTP_TOO_MANY_REQUESTS:
                    retry_after = float(e.response.headers.get("Retry-After", 60))
                    self.rate_limiter.mark_rate_limited(retry_after)
                    raise
                if e.response.status_code >= HTTP_SERVER_ERROR:
                    self.rate_limiter.mark_error()
                    raise
                raise  # Client error, don't retry

    def _handle_response_status(self, response: httpx.Response) -> None:
        """Handle HTTP response status."""
        response.raise_for_status()


class EmbeddingRouter:
    """Routes embedding requests to optimal endpoint based on availability."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_batch_size: int = 100,
        timeout: float = 60.0,
    ):
        """Initialize router with dual queues.

        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            max_batch_size: Maximum texts per batch request
            timeout: HTTP timeout in seconds

        """
        effective_api_key = api_key or get_google_api_key()

        # Create dual rate limiters
        self.batch_limiter = RateLimiter(EndpointType.BATCH)
        self.single_limiter = RateLimiter(EndpointType.SINGLE)

        # Create dual queues
        self.batch_queue = EndpointQueue(
            endpoint_type=EndpointType.BATCH,
            rate_limiter=self.batch_limiter,
            max_batch_size=max_batch_size,
            api_key=effective_api_key,
            timeout=timeout,
        )
        self.single_queue = EndpointQueue(
            endpoint_type=EndpointType.SINGLE,
            rate_limiter=self.single_limiter,
            max_batch_size=1,
            api_key=effective_api_key,
            timeout=timeout,
        )

    async def start(self) -> None:
        """Start background workers."""
        await self.batch_queue.start()
        await self.single_queue.start()
        logger.info("Embedding router started with dual-queue architecture")

    async def stop(self) -> None:
        """Stop background workers."""
        await self.batch_queue.stop()
        await self.single_queue.stop()
        logger.info("Embedding router stopped")

    async def embed(
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

        # Priority routing: single (low latency) first, then batch (fallback)
        if self.single_queue.is_available():
            # Single endpoint available - use it for low latency
            logger.debug("Routing %d text(s) to single endpoint (low latency)", len(texts_list))
            try:
                return await self.single_queue.submit(texts_list, task_type)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == HTTP_TOO_MANY_REQUESTS and self.batch_queue.is_available():
                    # Got 429 on single, fallback to batch
                    logger.info("Single endpoint hit rate limit, falling back to batch endpoint")
                    return await self.batch_queue.submit(texts_list, task_type)
                raise
        if self.batch_queue.is_available():
            # Single exhausted, fallback to batch
            logger.debug("Single endpoint exhausted, routing %d texts to batch endpoint", len(texts_list))
            try:
                return await self.batch_queue.submit(texts_list, task_type)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == HTTP_TOO_MANY_REQUESTS and self.single_queue.is_available():
                    # Got 429 on batch, fallback to single
                    logger.info("Batch endpoint hit rate limit, falling back to single endpoint")
                    return await self.single_queue.submit(texts_list, task_type)
                raise
        # Both exhausted - wait for single (lower latency)
        logger.debug("Both endpoints rate-limited, waiting for single endpoint")
        return await self.single_queue.submit(texts_list, task_type)


# Global singleton
_router: EmbeddingRouter | None = None
_router_lock = asyncio.Lock()


async def get_router(
    *,
    api_key: str | None = None,
    max_batch_size: int = 100,
    timeout: float = 60.0,
) -> EmbeddingRouter:
    """Get or create global embedding router singleton.

    Args:
        api_key: Google API key (defaults to GOOGLE_API_KEY env var)
        max_batch_size: Maximum texts per batch request
        timeout: HTTP timeout in seconds

    Returns:
        Shared EmbeddingRouter instance

    """
    global _router
    async with _router_lock:
        if _router is None:
            _router = EmbeddingRouter(
                api_key=api_key,
                max_batch_size=max_batch_size,
                timeout=timeout,
            )
            await _router.start()
    return _router


async def shutdown_router() -> None:
    """Shutdown global router (for cleanup)."""
    global _router
    async with _router_lock:
        if _router is not None:
            await _router.stop()
            _router = None


__all__ = [
    "EmbeddingRouter",
    "EndpointType",
    "RateLimitState",
    "get_router",
    "shutdown_router",
]
