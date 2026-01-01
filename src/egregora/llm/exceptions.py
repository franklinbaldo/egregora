"""Exceptions for LLM-related operations."""

from typing import Any


class AllModelsExhaustedError(Exception):
    """Raised when all LLM models have been tried and failed."""


class BatchJobFailedError(Exception):
    """Raised when a batch job fails."""

    def __init__(self, message: str, job_name: str, error_payload: Any) -> None:
        super().__init__(message)
        self.job_name = job_name
        self.error_payload = error_payload


class BatchJobTimeoutError(Exception):
    """Raised when a batch job times out."""

    def __init__(self, message: str, job_name: str) -> None:
        super().__init__(message)
        self.job_name = job_name


class BatchResultDownloadError(Exception):
    """Raised when a batch job result cannot be downloaded."""

    def __init__(self, message: str, url: str) -> None:
        super().__init__(message)
        self.url = url


class InvalidLLMResponseError(Exception):
    """Raised when the LLM response is invalid or cannot be parsed."""
