"""Dual-queue embedding router with independent rate limit tracking.

Routes embedding requests to either single or batch Google Gemini API endpoints
based on availability, maximizing throughput by using whichever endpoint is available.

Architecture:
    - Two independent queues (single + batch)
    - Two independent rate limiters
    - Smart routing: prefer batch for efficiency, fallback to single when rate-limited
    - Request accumulation during rate limit waits
    - Thread-based concurrency (synchronous I/O)
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any

import httpx

from egregora.config import EMBEDDING_DIM
from egregora.exceptions import EgregoraError
from egregora.llm.api_keys import get_google_api_key, get_google_api_keys

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


# Constants
GENAI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500

# Type alias for task type
TaskType = str


class EmbeddingError(EgregoraError):
    """Exception raised for embedding API errors with detailed error message."""

    def __init__(
        self, message: str, status_code: int | None = None, response_text: str | None = None
    ) -> None:
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(message)

    @classmethod
    def from_http_error(cls, e: httpx.HTTPStatusError, context: str = "") -> EmbeddingError:
        """Create EmbeddingError from HTTPStatusError with response details."""
        try:
            # Try to parse JSON error response
            error_data = e.response.json()
            if isinstance(error_data, dict):
                # Handle both {"error": {"message": "..."}} and {"error": "message"}
                error_field = error_data.get("error", error_data)
                if isinstance(error_field, dict):
                    error_message = error_field.get("message", str(error_data))
                else:
                    error_message = str(error_field)
            else:
                error_message = str(error_data)
        except (ValueError, KeyError):
            # Fall back to raw response text
            error_message = e.response.text or str(e)

        full_message = f"{context}: {error_message}" if context else error_message
        return cls(full_message, status_code=e.response.status_code, response_text=e.response.text)


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
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_available(self) -> bool:
        """Check if endpoint is available for requests."""
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            self.state = RateLimitState.AVAILABLE
            self.consecutive_errors = 0
            self.available_at = 0.0


@dataclass
class EmbeddingRequest:
    """A pending embedding request."""

    texts: list[str]
    task_type: str
    future: Future[list[list[float]]]
    submitted_at: float = field(default_factory=time.time)


@dataclass
class EndpointQueue:
    """Queue and worker for a single endpoint type."""

    endpoint_type: EndpointType
    rate_limiter: RateLimiter
    model: str  # Google model name (e.g., "models/gemini-embedding-001")
    queue: queue.Queue[EmbeddingRequest] = field(default_factory=queue.Queue)
    worker_thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    max_batch_size: int = 100
    api_key: str = field(default_factory=get_google_api_key)
    timeout: float = 60.0
    # Key cycling support
    _api_keys: list[str] = field(default_factory=list)
    _current_key_idx: int = 0

    def __post_init__(self) -> None:
        """Initialize API keys list for cycling."""
        self._api_keys = get_google_api_keys()
        if not self._api_keys and self.api_key:
            self._api_keys = [self.api_key]
        if self._api_keys:
            self.api_key = self._api_keys[0]
            logger.info("[EmbeddingRouter] Initialized with %d API keys", len(self._api_keys))

    def _next_key(self) -> str | None:
        """Advance to next API key on rate limit."""
        if len(self._api_keys) <= 1:
            return None
        self._current_key_idx = (self._current_key_idx + 1) % len(self._api_keys)
        self.api_key = self._api_keys[self._current_key_idx]
        # For security, do not log any portion of the API key.
        logger.info("[EmbeddingRouter] Rotated to next API key (index %d)", self._current_key_idx)
        return self.api_key

    def start(self) -> None:
        """Start background worker."""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.stop_event.clear()
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            logger.info("Started %s endpoint worker", self.endpoint_type.value)

    def stop(self) -> None:
        """Stop background worker."""
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            # Wake up worker if blocked on queue.get
            # We can't easily interrupt queue.get, but we can put a sentinel or rely on daemon thread
            # For clean shutdown, we can put a dummy request or just let it die if daemon=True
            # But let's try to join
            self.worker_thread.join(timeout=1.0)
            logger.info("Stopped %s endpoint worker", self.endpoint_type.value)

    def submit(self, texts: list[str], task_type: str) -> list[list[float]]:
        """Submit request and wait for result."""
        future: Future[list[list[float]]] = Future()
        request = EmbeddingRequest(texts, task_type, future)
        self.queue.put(request)
        return future.result()

    def is_available(self) -> bool:
        """Check if endpoint is available."""
        return self.rate_limiter.is_available()

    def _worker(self) -> None:
        """Background worker that processes queue."""
        while not self.stop_event.is_set():
            try:
                # Wait for first request with timeout to check stop_event
                try:
                    first_request = self.queue.get(timeout=1.0)
                except queue.Empty:
                    continue

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
                                # Note: queue.Queue doesn't support push_front easily.
                                # This is a limitation. We should be careful not to over-fetch.
                                # But since we are the only consumer, we can just process what we have
                                # and put the extra one back? No, LIFO is not guaranteed.
                                # Better strategy: peek or just accept we might process slightly less optimal batches
                                # if we have to put it back.
                                # Actually, standard Queue is FIFO. Putting back goes to end.
                                # This might reorder requests.
                                # Correct approach: Don't fetch if we can't fit?
                                # But we don't know size until we fetch.
                                # Workaround: Put it back and accept reordering, OR use a deque for local buffer.
                                # For simplicity, let's just put it back. Reordering within milliseconds is fine.
                                self.queue.put(req)
                                break
                        except queue.Empty:
                            break

                # Wait if rate limited
                while not self.rate_limiter.is_available() and not self.stop_event.is_set():
                    wait_time = max(0.1, self.rate_limiter.available_at - time.time())
                    logger.debug(
                        "%s endpoint waiting %.1fs for rate limit window", self.endpoint_type.value, wait_time
                    )
                    time.sleep(min(wait_time, 1.0))

                if self.stop_event.is_set():
                    break

                # Process accumulated requests
                self._process_batch(requests)

            except Exception:
                logger.exception("Unexpected error in %s worker", self.endpoint_type.value)
                time.sleep(1.0)  # Brief pause before continuing

    def _process_batch(self, requests: list[EmbeddingRequest]) -> None:
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
                    embeddings = self._call_single_endpoint(all_texts, task_type)
                else:
                    embeddings = self._call_batch_endpoint(all_texts, task_type)

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

    def _call_single_endpoint(self, texts: list[str], task_type: str) -> list[list[float]]:
        """Call /embedContent for each text."""
        embeddings = []
        with httpx.Client(timeout=self.timeout) as client:
            for text in texts:
                payload: dict[str, Any] = {
                    "model": self.model,
                    "content": {"parts": [{"text": text}]},
                    "outputDimensionality": EMBEDDING_DIM,
                    "taskType": task_type,
                }
                url = f"{GENAI_API_BASE}/{self.model}:embedContent"

                try:
                    response = client.post(url, params={"key": self.api_key}, json=payload)
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
                    # Client error - include detailed error message
                    raise EmbeddingError.from_http_error(
                        e, f"Single endpoint failed for text: {text[:50]}..."
                    ) from e

        return embeddings

    def _call_batch_endpoint(self, texts: list[str], task_type: str) -> list[list[float]]:
        """Call /batchEmbedContents for multiple texts."""
        requests_payload = []
        for text in texts:
            req: dict[str, Any] = {
                "model": self.model,
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": EMBEDDING_DIM,
                "taskType": task_type,
            }
            requests_payload.append(req)

        payload = {"requests": requests_payload}
        url = f"{GENAI_API_BASE}/{self.model}:batchEmbedContents"

        with httpx.Client(timeout=self.timeout) as client:
            try:
                response = client.post(url, params={"key": self.api_key}, json=payload)
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

            except httpx.HTTPStatusError as e:
                if e.response.status_code == HTTP_TOO_MANY_REQUESTS:
                    # Try next key if available
                    next_key = self._next_key()
                    if next_key and self._current_key_idx != 0:
                        # Retry with new key - recursive call
                        return self._call_batch_endpoint(texts, task_type)
                    # All keys exhausted or only one key
                    retry_after = float(e.response.headers.get("Retry-After", 60))
                    self.rate_limiter.mark_rate_limited(retry_after)
                    raise
                if e.response.status_code >= HTTP_SERVER_ERROR:
                    self.rate_limiter.mark_error()
                    raise
                # Client error - include detailed error message
                raise EmbeddingError.from_http_error(
                    e, f"Batch endpoint failed for {len(texts)} texts"
                ) from e
            else:
                return embeddings

    def _handle_response_status(self, response: httpx.Response) -> None:
        """Handle HTTP response status."""
        response.raise_for_status()


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
        """Initialize router with dual queues.

        Args:
            model: Google embedding model (e.g., "models/gemini-embedding-001")
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
            model=model,
            max_batch_size=max_batch_size,
            api_key=effective_api_key,
            timeout=timeout,
        )
        self.single_queue = EndpointQueue(
            endpoint_type=EndpointType.SINGLE,
            rate_limiter=self.single_limiter,
            model=model,
            max_batch_size=1,
            api_key=effective_api_key,
            timeout=timeout,
        )

    def start(self) -> None:
        """Start background workers."""
        self.batch_queue.start()
        self.single_queue.start()
        logger.info("Embedding router started with dual-queue architecture")

    def stop(self) -> None:
        """Stop background workers."""
        self.batch_queue.stop()
        self.single_queue.stop()
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

        # Priority routing: single (low latency) first, then batch (fallback)
        if self.single_queue.is_available():
            # Single endpoint available - use it for low latency
            logger.debug("Routing %d text(s) to single endpoint (low latency)", len(texts_list))
            try:
                return self.single_queue.submit(texts_list, task_type)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == HTTP_TOO_MANY_REQUESTS and self.batch_queue.is_available():
                    # Got 429 on single, fallback to batch
                    logger.info("Single endpoint hit rate limit, falling back to batch endpoint")
                    return self.batch_queue.submit(texts_list, task_type)
                raise
        if self.batch_queue.is_available():
            # Single exhausted, fallback to batch
            logger.debug("Single endpoint exhausted, routing %d texts to batch endpoint", len(texts_list))
            try:
                return self.batch_queue.submit(texts_list, task_type)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == HTTP_TOO_MANY_REQUESTS and self.single_queue.is_available():
                    # Got 429 on batch, fallback to single
                    logger.info("Batch endpoint hit rate limit, falling back to single endpoint")
                    return self.single_queue.submit(texts_list, task_type)
                raise
        # Both exhausted - wait for single (lower latency)
        logger.debug("Both endpoints rate-limited, waiting for single endpoint")
        return self.single_queue.submit(texts_list, task_type)


# Global singleton
_router: EmbeddingRouter | None = None
_router_lock = threading.Lock()


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
    """Get or create global embedding router singleton.

    Prefer :func:`create_embedding_router` when the caller owns lifecycle
    management. This helper is kept for backwards compatibility.
    """
    global _router
    with _router_lock:
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
    with _router_lock:
        if _router is not None:
            _router.stop()
            _router = None


def validate_api_key(api_key: str | None = None, *, model: str = "models/gemini-2.0-flash-exp") -> None:
    """Validate Gemini API key with a lightweight API call.

    This function performs a quick validation of the API key by making a
    lightweight count_tokens request. Use this for fail-fast validation
    before running expensive operations.

    Args:
        api_key: Google API key to validate. If None, uses GOOGLE_API_KEY env var.
        model: Model to use for validation (default: gemini-2.0-flash-exp).

    Raises:
        EmbeddingError: If the API key is invalid or expired.
        ValueError: If no API key is provided or found in environment.

    Example:
        >>> try:
        ...     validate_api_key()
        ...     print("API key is valid!")
        ... except EmbeddingError as e:
        ...     print(f"Invalid API key: {e}")

    """
    effective_key = api_key or get_google_api_key()
    if not effective_key:
        msg = "No API key provided and GOOGLE_API_KEY environment variable not set"
        raise ValueError(msg)

    # Use countTokens as a lightweight validation call
    url = f"{GENAI_API_BASE}/{model}:countTokens"
    payload = {"contents": [{"parts": [{"text": "test"}]}]}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, params={"key": effective_key}, json=payload)
            response.raise_for_status()
            logger.debug("API key validation successful")
    except httpx.HTTPStatusError as e:
        raise EmbeddingError.from_http_error(e, "API key validation failed") from e
    except httpx.RequestError as e:
        msg = f"API key validation failed: network error - {e}"
        raise EmbeddingError(msg) from e


__all__ = [
    "EmbeddingError",
    "EmbeddingRouter",
    "EndpointType",
    "RateLimitState",
    "TaskType",
    "create_embedding_router",
    "get_router",
    "shutdown_router",
    "validate_api_key",
]
