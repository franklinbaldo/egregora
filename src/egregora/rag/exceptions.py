"""Custom exceptions for RAG (Retrieval-Augmented Generation) module."""

from __future__ import annotations

from egregora.exceptions import EgregoraError


class RAGError(EgregoraError):
    """Base exception for all RAG-related errors."""


class EmbeddingError(RAGError):
    """Base exception for embedding-related errors."""


class EmbeddingAPIError(EmbeddingError):
    """Raised when the embedding API request fails.

    This wraps HTTP errors and network issues, hiding the underlying
    HTTP library implementation details.
    """

    def __init__(self, message: str, *, status_code: int | None = None, original_error: Exception | None = None):
        """Initialize the API error.

        Args:
            message: Error message describing what went wrong
            status_code: Optional HTTP status code if applicable
            original_error: Optional original exception that was wrapped
        """
        self.status_code = status_code
        self.original_error = original_error
        super().__init__(message)


class EmbeddingValidationError(EmbeddingError):
    """Raised when embedding response validation fails.

    This indicates the API returned successfully but the response
    format was unexpected or invalid.
    """


class RateLimitError(EmbeddingAPIError):
    """Raised when API rate limit is exceeded.

    This is a specific type of API error that indicates temporary
    overload and can be retried after a delay.
    """

    def __init__(self, message: str = "Rate limit exceeded", *, retry_after: float | None = None):
        """Initialize the rate limit error.

        Args:
            message: Error message
            retry_after: Optional number of seconds to wait before retrying
        """
        super().__init__(message, status_code=429)
        self.retry_after = retry_after
