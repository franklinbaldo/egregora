"""Exceptions for LLM-related operations."""


class AllModelsExhaustedError(Exception):
    """Raised when all LLM models have been tried and failed."""


class BatchJobFailedError(Exception):
    """Raised when a batch job fails."""


class BatchJobTimeoutError(Exception):
    """Raised when a batch job times out."""


class BatchResultDownloadError(Exception):
    """Raised when a batch job result cannot be downloaded."""


class InvalidLLMResponseError(Exception):
    """Raised when the LLM response is invalid or cannot be parsed."""
