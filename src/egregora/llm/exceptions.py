"""Custom exceptions for LLM provider interactions."""

from egregora.exceptions import EgregoraError


class LLMProviderError(EgregoraError):
    """Base exception for all LLM provider related errors."""


class AllModelsExhaustedError(LLMProviderError):
    """Raised when all models and keys have been tried and failed."""

    def __init__(self, message: str, causes: list[Exception] | None = None) -> None:
        self.causes = causes or []
        super().__init__(message)


class AllApiKeysExhaustedError(LLMProviderError):
    """Raised when all API keys have been exhausted for a provider."""


class BatchJobError(LLMProviderError):
    """Base exception for errors related to batch job processing."""

    def __init__(self, message: str, job_name: str | None = None) -> None:
        self.job_name = job_name
        super().__init__(f"{message}. Job: {job_name}" if job_name else message)


class BatchJobFailedError(BatchJobError):
    """Exception raised when a batch job completes in a failed state."""

    def __init__(
        self,
        message: str,
        job_name: str | None = None,
        error_payload: dict | None = None,
    ) -> None:
        self.error_payload = error_payload
        super().__init__(message, job_name)


class BatchJobTimeoutError(BatchJobError):
    """Exception raised when polling a batch job for completion times out."""


class BatchResultDownloadError(LLMProviderError):
    """Exception raised when results of a batch job cannot be downloaded."""

    def __init__(self, message: str, url: str) -> None:
        self.url = url
        super().__init__(f"{message}. URL: {url}")


class InvalidLLMResponseError(LLMProviderError):
    """Exception raised when the LLM response is empty or invalid."""
