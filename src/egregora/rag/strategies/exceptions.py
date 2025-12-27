"""Custom exceptions for RAG embedding strategies.

Following defensive programming principles - fail fast, fail clearly.
"""

from __future__ import annotations


class EmbeddingStrategyError(Exception):
    """Base exception for embedding strategy errors."""

    pass


class ProviderNotAvailableError(EmbeddingStrategyError):
    """Raised when an embedding provider is not available (missing API key, etc.)."""

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"Embedding provider '{provider}' not available: {reason}")


class UnsupportedModelError(EmbeddingStrategyError):
    """Raised when a model format is not supported by any strategy."""

    def __init__(self, model: str):
        self.model = model
        super().__init__(
            f"Unsupported embedding model format: {model}\n"
            f"Supported formats:\n"
            f"  - Gemini: models/gemini-embedding-001\n"
            f"  - OpenRouter: qwen/qwen3-embedding-0.6b"
        )


class EmbeddingDimensionMismatchError(EmbeddingStrategyError):
    """Raised when embedding dimensions don't match expected dimensions."""

    def __init__(self, expected: int, actual: int, model: str):
        self.expected = expected
        self.actual = actual
        self.model = model
        super().__init__(
            f"Embedding dimension mismatch for model '{model}': "
            f"expected {expected}, got {actual}"
        )


class EmbeddingAPIError(EmbeddingStrategyError):
    """Raised when the embedding API call fails."""

    def __init__(self, provider: str, status_code: int | None, message: str):
        self.provider = provider
        self.status_code = status_code
        self.message = message
        status_info = f" (HTTP {status_code})" if status_code else ""
        super().__init__(f"{provider} API error{status_info}: {message}")


__all__ = [
    "EmbeddingStrategyError",
    "ProviderNotAvailableError",
    "UnsupportedModelError",
    "EmbeddingDimensionMismatchError",
    "EmbeddingAPIError",
]
