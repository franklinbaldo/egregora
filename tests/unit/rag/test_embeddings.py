"""Behavioral tests for RAG embedding generation.

Tests verify WHAT the embedding API does, not HOW it does it.
Focus on public API contracts, edge cases, and error handling.
"""

import pytest
import respx
from httpx import Response

from egregora.config.exceptions import ApiKeyNotFoundError
from egregora.rag.embeddings import (
    embed_chunks,
    embed_query_text,
    embed_text,
    embed_texts_in_batch,
    is_rag_available,
)
from egregora.rag.exceptions import EmbeddingAPIError, EmbeddingValidationError, RateLimitError


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Mock time.sleep to avoid waiting in retry loops during tests."""
    monkeypatch.setattr("time.sleep", lambda x: None)


class TestIsRagAvailable:
    """Test RAG availability check behavior."""

    def test_returns_true_when_api_key_available(self, monkeypatch):
        """Should return True when GOOGLE_API_KEY is set."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        assert is_rag_available() is True

    def test_returns_false_when_no_api_key(self, monkeypatch):
        """Should return False when no API key is available."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        assert is_rag_available() is False


class TestEmbedText:
    """Test single text embedding behavior."""

    @respx.mock
    def test_returns_768_dimensional_vector(self, monkeypatch):
        """Should return a 768-dimensional embedding vector for valid text."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        # Mock successful API response
        mock_embedding = [0.1] * 768  # 768-dimensional vector
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
        ).mock(
            return_value=Response(
                200,
                json={"embedding": {"values": mock_embedding}},
            )
        )

        result = embed_text("Hello world", model="models/text-embedding-004")

        assert isinstance(result, list)
        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)

    @respx.mock
    def test_raises_validation_error_on_missing_embedding(self, monkeypatch):
        """Should raise EmbeddingValidationError when API returns invalid response."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        # Mock API response with missing embedding
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
        ).mock(
            return_value=Response(200, json={})  # No "embedding" key
        )

        with pytest.raises(EmbeddingValidationError, match="No embedding in response"):
            embed_text("test", model="models/text-embedding-004")

    @respx.mock
    def test_raises_rate_limit_error_on_429(self, monkeypatch):
        """Should raise RateLimitError when API returns 429 status."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
        ).mock(return_value=Response(429, json={"error": "Rate limit exceeded"}))

        with pytest.raises(RateLimitError):
            embed_text("test", model="models/text-embedding-004")

    @respx.mock
    def test_raises_api_error_on_500(self, monkeypatch):
        """Should raise EmbeddingAPIError on server errors (5xx)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
        ).mock(return_value=Response(500, json={"error": "Internal server error"}))

        with pytest.raises(EmbeddingAPIError, match="API server error"):
            embed_text("test", model="models/text-embedding-004")

    @respx.mock
    def test_raises_api_error_on_400(self, monkeypatch):
        """Should raise EmbeddingAPIError on client errors (4xx except 429)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
        ).mock(return_value=Response(400, json={"error": "Bad request"}))

        with pytest.raises(EmbeddingAPIError, match="API client error"):
            embed_text("test", model="models/text-embedding-004")

    def test_raises_value_error_when_no_api_key(self, monkeypatch):
        """Should raise ApiKeyNotFoundError when API key is not configured."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        with pytest.raises(ApiKeyNotFoundError, match=r"not set.*GOOGLE_API_KEY"):
            embed_text("test", model="models/text-embedding-004")

    @respx.mock
    def test_uses_provided_api_key_over_env(self, monkeypatch):
        """Should use explicitly provided API key instead of environment variable."""
        monkeypatch.setenv("GOOGLE_API_KEY", "env-key")

        mock_embedding = [0.1] * 768
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
        ).mock(return_value=Response(200, json={"embedding": {"values": mock_embedding}}))

        embed_text("test", model="models/text-embedding-004", api_key="explicit-key")

        # Verify the explicit key was used in query params
        assert route.calls[0].request.url.params["key"] == "explicit-key"


class TestEmbedTextsInBatch:
    """Test batch text embedding behavior."""

    @respx.mock
    def test_returns_list_of_vectors_for_multiple_texts(self, monkeypatch):
        """Should return a list of embedding vectors for batch of texts."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        # Mock batch API response
        mock_embeddings = [
            {"values": [0.1] * 768},
            {"values": [0.2] * 768},
            {"values": [0.3] * 768},
        ]
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents"
        ).mock(return_value=Response(200, json={"embeddings": mock_embeddings}))

        texts = ["first", "second", "third"]
        result = embed_texts_in_batch(texts, model="models/text-embedding-004")

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(len(vec) == 768 for vec in result)

    @respx.mock
    def test_handles_empty_list(self, monkeypatch):
        """Should return empty list for empty input."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        result = embed_texts_in_batch([], model="models/text-embedding-004")
        assert result == []

    @respx.mock
    def test_raises_validation_error_on_missing_embeddings(self, monkeypatch):
        """Should raise EmbeddingValidationError when batch response is invalid."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents"
        ).mock(return_value=Response(200, json={}))  # Missing "embeddings" key

        with pytest.raises(EmbeddingValidationError, match="No embeddings in batch response"):
            embed_texts_in_batch(["test"], model="models/text-embedding-004")


class TestEmbedChunks:
    """Test chunk embedding behavior."""

    @respx.mock
    def test_embeds_multiple_chunks(self, monkeypatch):
        """Should embed a list of text chunks."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        mock_embeddings = [
            {"values": [0.1] * 768},
            {"values": [0.2] * 768},
        ]
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents"
        ).mock(return_value=Response(200, json={"embeddings": mock_embeddings}))

        chunks = ["chunk1", "chunk2"]
        result = embed_chunks(chunks, model="models/text-embedding-004")

        assert len(result) == 2
        assert all(len(vec) == 768 for vec in result)


class TestEmbedQueryText:
    """Test query text embedding behavior."""

    @respx.mock
    def test_embeds_query_with_retrieval_task_type(self, monkeypatch):
        """Should embed query text with RETRIEVAL_QUERY task type."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        # embed_query_text() uses batch endpoint internally
        mock_embeddings = [{"values": [0.1] * 768}]
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents"
        ).mock(return_value=Response(200, json={"embeddings": mock_embeddings}))

        embed_query_text("search query", model="models/text-embedding-004")

        # Verify RETRIEVAL_QUERY task type was used
        request_body = route.calls[0].request.content
        assert b"RETRIEVAL_QUERY" in request_body

    @respx.mock
    def test_returns_768_dimensional_vector(self, monkeypatch):
        """Should return a 768-dimensional vector for query text."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        # embed_query_text() uses batch endpoint and returns first element
        mock_embeddings = [{"values": [0.1] * 768}]
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents"
        ).mock(return_value=Response(200, json={"embeddings": mock_embeddings}))

        result = embed_query_text("query", model="models/text-embedding-004")

        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)
