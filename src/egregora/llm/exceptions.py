"""Custom exceptions for the LLM module."""
from typing import Any

class LLMError(Exception):
    """Base class for LLM-related errors."""
    pass

class ApiKeyNotFoundError(LLMError):
    """Raised when an API key is not found in the environment."""

    def __init__(self, key_name: str):
        self.key_name = key_name
        super().__init__(f"{key_name} environment variable not set.")


class BatchJobFailedError(LLMError):
    """Raised when a batch job fails."""
    def __init__(self, message: str, job_name: str, error_payload: Any | None = None):
        super().__init__(f"{message}: {job_name}")
        self.job_name = job_name
        self.error_payload = error_payload


class BatchJobTimeoutError(LLMError):
    """Raised when a batch job times out."""
    def __init__(self, message: str, job_name: str):
        super().__init__(f"{message}: {job_name}")
        self.job_name = job_name

class BatchResultDownloadError(LLMError):
    """Raised when downloading batch results fails."""
    def __init__(self, message: str, url: str):
        super().__init__(f"{message}: {url}")
        self.url = url

class InvalidLLMResponseError(LLMError):
    """Raised when the LLM response is invalid."""
    pass

class AllModelsExhaustedError(LLMError):
    def __init__(self, message: str, causes: list[Exception] | None = None):
        super().__init__(message)
        self.causes = causes
    """Raised when all models in the rotator have been exhausted."""
    pass

