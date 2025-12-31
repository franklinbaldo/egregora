"""Custom exceptions for LLM-related errors."""

from typing import Any


class AllModelsExhaustedError(Exception):
    """Raised when all models and keys are exhausted."""

    def __init__(self, message: str, causes: list[Exception] | None = None) -> None:
        super().__init__(message)
        self.causes = causes or []


class BatchJobFailedError(Exception):
    """Raised when a batch job fails."""

    def __init__(self, message: str, job_name: str, error_payload: Any) -> None:
        super().__init__(f"{message}: {job_name} -> {error_payload}")
        self.job_name = job_name
        self.error_payload = error_payload


class BatchJobTimeoutError(Exception):
    """Raised when a batch job times out."""

    def __init__(self, message: str, job_name: str) -> None:
        super().__init__(f"{message}: {job_name}")
        self.job_name = job_name


class BatchResultDownloadError(Exception):
    """Raised when a batch result cannot be downloaded."""

    def __init__(self, message: str, url: str) -> None:
        super().__init__(f"{message}: {url}")
        self.url = url


class InvalidLLMResponseError(Exception):
    """Raised when an LLM response is invalid."""
