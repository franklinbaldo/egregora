"""Tests for RAG exception classes."""

import pytest

from egregora.exceptions import EgregoraError
from egregora.rag.exceptions import (
    EmbeddingAPIError,
    EmbeddingError,
    EmbeddingValidationError,
    RAGError,
    RateLimitError,
)


class TestRAGError:
    """Tests for RAGError base exception."""

    def test_inherits_from_egregora_error(self):
        """RAGError should inherit from EgregoraError."""
        assert issubclass(RAGError, EgregoraError)

    def test_can_be_instantiated(self):
        """RAGError can be created with a message."""
        error = RAGError("Test error")
        assert str(error) == "Test error"


class TestEmbeddingError:
    """Tests for EmbeddingError base exception."""

    def test_inherits_from_rag_error(self):
        """EmbeddingError should inherit from RAGError."""
        assert issubclass(EmbeddingError, RAGError)

    def test_can_be_raised_and_caught(self):
        """EmbeddingError can be raised and caught."""
        with pytest.raises(EmbeddingError) as exc_info:
            msg = "Embedding failed"
            raise EmbeddingError(msg)
        assert "Embedding failed" in str(exc_info.value)


class TestEmbeddingAPIError:
    """Tests for EmbeddingAPIError."""

    def test_basic_error_message(self):
        """Error should store and display message."""
        error = EmbeddingAPIError("API request failed")
        assert str(error) == "API request failed"

    def test_with_status_code(self):
        """Error should store HTTP status code."""
        error = EmbeddingAPIError("Bad request", status_code=400)
        assert error.status_code == 400
        assert "Bad request" in str(error)

    def test_with_original_error(self):
        """Error should wrap original exception."""
        original = ValueError("Network timeout")
        error = EmbeddingAPIError("API failed", original_error=original)
        assert error.original_error is original
        assert isinstance(error.original_error, ValueError)

    def test_with_all_parameters(self):
        """Error should handle all parameters together."""
        original = RuntimeError("Connection refused")
        error = EmbeddingAPIError(
            "Failed to connect to API",
            status_code=503,
            original_error=original,
        )
        assert str(error) == "Failed to connect to API"
        assert error.status_code == 503
        assert error.original_error is original

    def test_none_status_code_by_default(self):
        """Status code should be None if not provided."""
        error = EmbeddingAPIError("Generic error")
        assert error.status_code is None

    def test_none_original_error_by_default(self):
        """Original error should be None if not provided."""
        error = EmbeddingAPIError("Generic error")
        assert error.original_error is None


class TestEmbeddingValidationError:
    """Tests for EmbeddingValidationError."""

    def test_inherits_from_embedding_error(self):
        """EmbeddingValidationError should inherit from EmbeddingError."""
        assert issubclass(EmbeddingValidationError, EmbeddingError)

    def test_indicates_validation_failure(self):
        """Error should clearly indicate validation failure."""
        error = EmbeddingValidationError("No embedding in response")
        assert "No embedding in response" in str(error)

    def test_can_be_caught_as_embedding_error(self):
        """Validation errors can be caught as EmbeddingError."""
        with pytest.raises(EmbeddingError):
            msg = "Invalid response format"
            raise EmbeddingValidationError(msg)


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_inherits_from_api_error(self):
        """RateLimitError should inherit from EmbeddingAPIError."""
        assert issubclass(RateLimitError, EmbeddingAPIError)

    def test_default_message(self):
        """Rate limit error should have sensible default message."""
        error = RateLimitError()
        assert "Rate limit exceeded" in str(error)

    def test_status_code_is_429(self):
        """Rate limit errors should always have 429 status code."""
        error = RateLimitError()
        assert error.status_code == 429

    def test_custom_message(self):
        """Rate limit error should accept custom message."""
        error = RateLimitError("Too many requests to embedding API")
        assert "Too many requests" in str(error)
        assert error.status_code == 429

    def test_with_retry_after(self):
        """Error should store retry-after delay."""
        error = RateLimitError(retry_after=60.0)
        assert error.retry_after == 60.0

    def test_retry_after_none_by_default(self):
        """Retry-after should be None if not provided."""
        error = RateLimitError()
        assert error.retry_after is None

    def test_with_all_parameters(self):
        """Error should handle message and retry-after together."""
        error = RateLimitError("Rate limited", retry_after=120.5)
        assert "Rate limited" in str(error)
        assert error.retry_after == 120.5
        assert error.status_code == 429


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_all_rag_errors_catchable_as_egregora_error(self):
        """All RAG exceptions should be catchable as EgregoraError."""
        exceptions = [
            RAGError("test"),
            EmbeddingError("test"),
            EmbeddingAPIError("test"),
            EmbeddingValidationError("test"),
            RateLimitError("test"),
        ]

        for exc in exceptions:
            with pytest.raises(EgregoraError):
                raise exc

    def test_embedding_errors_catchable_as_rag_error(self):
        """All embedding exceptions should be catchable as RAGError."""
        exceptions = [
            EmbeddingError("test"),
            EmbeddingAPIError("test"),
            EmbeddingValidationError("test"),
            RateLimitError("test"),
        ]

        for exc in exceptions:
            with pytest.raises(RAGError):
                raise exc

    def test_api_errors_catchable_as_embedding_error(self):
        """API exceptions should be catchable as EmbeddingError."""
        exceptions = [
            EmbeddingAPIError("test"),
            RateLimitError("test"),
        ]

        for exc in exceptions:
            with pytest.raises(EmbeddingError):
                raise exc
