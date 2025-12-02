"""Tests for dual-queue embedding router with rate limit handling.

Tests cover:
- Routing logic (single-first priority for low latency)
- Rate limit detection and backoff
- Request accumulation during rate limit waits
- Dual endpoint availability tracking
- Error handling and retries
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import httpx
import pytest

from egregora.rag.embedding_router import (
    GENAI_API_BASE,
    EmbeddingRouter,
    EndpointQueue,
    EndpointType,
    RateLimiter,
    RateLimitState,
)

# Test constants (smaller values for faster tests)
TEST_BATCH_SIZE = 3  # Small batch for testing accumulation behavior
TEST_TIMEOUT = 10.0  # Shorter timeout for faster test execution


def _create_response(status_code: int, **kwargs) -> httpx.Response:
    """Helper to create httpx.Response with required request parameter."""
    # Create a dummy request
    request = httpx.Request("POST", "https://example.com/api")
    return httpx.Response(status_code, request=request, **kwargs)


@pytest.fixture
def embedding_model():
    """Embedding model name for tests.

    Uses a simple test model name instead of loading from production settings.
    """
    return "models/test-embedding-001"


@pytest.fixture
def mock_api_key():
    """Mock API key for testing."""
    return "test-api-key-12345"


@pytest.fixture
def router(mock_api_key, embedding_model):
    """Create router and clean up after test.

    Uses configured embedding model from fixture.
    Uses small batch size (3) for testing batch accumulation behavior.
    Uses short timeout (10s) for faster test execution.
    """
    r = EmbeddingRouter(
        model=embedding_model,
        api_key=mock_api_key,
        max_batch_size=TEST_BATCH_SIZE,
        timeout=TEST_TIMEOUT,
    )
    r.start()
    yield r
    r.stop()


# ============================================================================
# RateLimiter Tests
# ============================================================================


def test_rate_limiter_initial_state():
    """Test rate limiter starts in AVAILABLE state."""
    limiter = RateLimiter(EndpointType.SINGLE)
    assert limiter.is_available()
    assert limiter.state == RateLimitState.AVAILABLE
    assert limiter.consecutive_errors == 0


def test_rate_limiter_mark_rate_limited():
    """Test marking endpoint as rate limited."""
    limiter = RateLimiter(EndpointType.BATCH)
    limiter.mark_rate_limited(retry_after=5.0)

    assert not limiter.is_available()
    assert limiter.state == RateLimitState.RATE_LIMITED
    assert limiter.available_at > 0


def test_rate_limiter_mark_error():
    """Test marking endpoint as having error."""
    limiter = RateLimiter(EndpointType.SINGLE)
    limiter.mark_error(backoff_seconds=2.0)

    assert not limiter.is_available()
    assert limiter.state == RateLimitState.ERROR
    assert limiter.consecutive_errors == 1


def test_rate_limiter_max_errors():
    """Test that max consecutive errors raises RuntimeError."""
    limiter = RateLimiter(EndpointType.BATCH, max_consecutive_errors=3)

    # First two errors should not raise
    limiter.mark_error()
    limiter.mark_error()

    # Third error should raise
    with pytest.raises(RuntimeError, match="failed 3 times"):
        limiter.mark_error()


def test_rate_limiter_mark_success():
    """Test that marking success resets state."""
    limiter = RateLimiter(EndpointType.SINGLE)
    limiter.mark_error()
    assert limiter.consecutive_errors == 1

    limiter.mark_success()
    assert limiter.is_available()
    assert limiter.consecutive_errors == 0
    assert limiter.state == RateLimitState.AVAILABLE


# ============================================================================
# Router Routing Logic Tests
# ============================================================================


def test_router_prefers_single_endpoint_for_low_latency(router, embedding_model):
    """Test that router prefers single endpoint for low latency."""
    with patch("httpx.Client.post") as mock_post:
        # Mock successful response
        mock_post.return_value = _create_response(
            200,
            json={"embedding": {"values": [0.1] * 768}},
        )

        # Both endpoints available - should use single for low latency
        embeddings = router.embed(["test text"], "RETRIEVAL_QUERY")

        assert len(embeddings) == 1
        assert len(embeddings[0]) == 768

        # Verify single endpoint was called
        assert mock_post.called
        call_url = str(mock_post.call_args[0][0])
        assert ":embedContent" in call_url, "Should use single endpoint for low latency"


def test_router_falls_back_to_batch_when_single_exhausted(router, embedding_model):
    """Test fallback to batch endpoint when single is rate-limited."""
    # Mark single endpoint as rate-limited
    router.single_limiter.mark_rate_limited(retry_after=60.0)

    with patch("httpx.Client.post") as mock_post:
        # Mock batch endpoint success
        mock_post.return_value = _create_response(
            200,
            json={"embeddings": [{"values": [0.1] * 768}, {"values": [0.2] * 768}]},
        )

        # Should fallback to batch
        embeddings = router.embed(["text1", "text2"], "RETRIEVAL_DOCUMENT")

        assert len(embeddings) == 2
        assert mock_post.called
        call_url = str(mock_post.call_args[0][0])
        assert ":batchEmbedContents" in call_url, "Should fallback to batch when single is exhausted"


def test_router_handles_429_rate_limit(router, embedding_model):
    """Test that router handles 429 rate limit responses."""
    with patch("httpx.Client.post") as mock_post:
        # First request returns 429, second succeeds
        mock_post.side_effect = [
            _create_response(429, headers={"Retry-After": "2"}),
            _create_response(200, json={"embeddings": [{"values": [0.1] * 768}]}),
        ]

        # Should hit rate limit on single, then use batch
        embeddings = router.embed(["test"], "RETRIEVAL_QUERY")

        assert len(embeddings) == 1
        assert not router.single_limiter.is_available(), "Single endpoint should be rate-limited"
        assert router.batch_limiter.is_available(), "Batch endpoint should still be available"
        assert mock_post.call_count == 2


def test_router_accumulates_requests_during_rate_limit(router, embedding_model):
    """Test that router accumulates requests when rate-limited."""
    # Both endpoints start rate-limited
    router.single_limiter.mark_rate_limited(retry_after=0.5)  # Short delay for test
    router.batch_limiter.mark_rate_limited(retry_after=0.5)

    with patch("httpx.Client.post") as mock_post:
        # Mock successful response after wait
        mock_post.return_value = _create_response(
            200,
            json={"embedding": {"values": [0.1] * 768}},
        )

        # Submit multiple requests concurrently
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(router.embed, ["text1"], "RETRIEVAL_QUERY"),
                executor.submit(router.embed, ["text2"], "RETRIEVAL_QUERY"),
                executor.submit(router.embed, ["text3"], "RETRIEVAL_QUERY"),
            ]
            results = [f.result() for f in futures]

        assert len(results) == 3
        assert all(len(r) == 1 for r in results)


# ============================================================================
# EndpointQueue Tests
# ============================================================================


def test_endpoint_queue_processes_single_request(mock_api_key, embedding_model):
    """Test that endpoint queue processes single request."""
    limiter = RateLimiter(EndpointType.SINGLE)
    queue = EndpointQueue(
        endpoint_type=EndpointType.SINGLE,
        rate_limiter=limiter,
        model=embedding_model,
        api_key=mock_api_key,
        timeout=TEST_TIMEOUT,
    )

    queue.start()

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = _create_response(
            200,
            json={"embedding": {"values": [0.1] * 768}},
        )

        result = queue.submit(["test text"], "RETRIEVAL_QUERY")

    queue.stop()

    assert len(result) == 1
    assert len(result[0]) == 768


def test_endpoint_queue_batches_multiple_requests(mock_api_key, embedding_model):
    """Test that batch endpoint accumulates multiple requests."""
    limiter = RateLimiter(EndpointType.BATCH)
    queue = EndpointQueue(
        endpoint_type=EndpointType.BATCH,
        rate_limiter=limiter,
        model=embedding_model,
        max_batch_size=TEST_BATCH_SIZE,  # Use small batch to test accumulation
        api_key=mock_api_key,
        timeout=TEST_TIMEOUT,
    )

    with patch("httpx.Client.post") as mock_post:
        # Mock batch endpoint response
        mock_post.return_value = _create_response(
            200,
            json={
                "embeddings": [
                    {"values": [0.1] * 768},
                    {"values": [0.2] * 768},
                    {"values": [0.3] * 768},
                ]
            },
        )

        queue.start()

        # Submit 3 requests that should be batched
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(queue.submit, ["text1"], "RETRIEVAL_DOCUMENT"),
                executor.submit(queue.submit, ["text2"], "RETRIEVAL_DOCUMENT"),
                executor.submit(queue.submit, ["text3"], "RETRIEVAL_DOCUMENT"),
            ]
            results = [f.result() for f in futures]

        queue.stop()

        assert len(results) == 3
        # Verify requests were processed
        assert mock_post.called, "At least one batch call should be made"


def test_endpoint_queue_handles_api_error(mock_api_key, embedding_model):
    """Test that queue handles API errors properly."""
    limiter = RateLimiter(EndpointType.SINGLE)
    queue = EndpointQueue(
        endpoint_type=EndpointType.SINGLE,
        rate_limiter=limiter,
        model=embedding_model,
        api_key=mock_api_key,
        timeout=TEST_TIMEOUT,
    )

    queue.start()

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = _create_response(400, json={"error": "Bad request"})

        with pytest.raises(httpx.HTTPStatusError):
            queue.submit(["test"], "RETRIEVAL_QUERY")

    queue.stop()


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_workflow_with_both_endpoints(router, embedding_model):
    """Test full workflow using both endpoints."""
    with patch("httpx.Client.post") as mock_post:
        # Mock responses: first for single endpoint, then for batch
        mock_post.side_effect = [
            _create_response(200, json={"embedding": {"values": [0.1] * 768}}),
            _create_response(200, json={
                "embeddings": [
                    {"values": [0.2] * 768},
                    {"values": [0.3] * 768},
                ]
            }),
        ]

        # First request goes to single (low latency)
        result1 = router.embed(["query1"], "RETRIEVAL_QUERY")
        assert len(result1) == 1

        # Mark single as rate-limited
        router.single_limiter.mark_rate_limited(retry_after=60.0)

        # Next request should use batch
        result2 = router.embed(["doc1", "doc2"], "RETRIEVAL_DOCUMENT")
        assert len(result2) == 2

        # Verify both endpoints were used
        assert mock_post.call_count == 2


def test_concurrent_requests_under_rate_limits(router, embedding_model):
    """Test handling concurrent requests with rate limit fallback."""
    with patch("httpx.Client.post") as mock_post:
        # All requests succeed (simplified test - just ensures concurrency works)
        mock_post.return_value = _create_response(200, json={"embedding": {"values": [0.1] * 768}})

        # Submit 3 concurrent requests
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(router.embed, [f"text{i}"], "RETRIEVAL_QUERY") for i in range(3)]
            results = [f.result() for f in futures]

        # All should succeed
        assert len(results) == 3
        assert all(len(r) == 1 for r in results)
        # Endpoint should have been used
        assert mock_post.called
