from __future__ import annotations

"""Shared retry configuration for tenacity-based retries.

This module exports configuration constants for consistent retry behavior across the codebase.
Use tenacity decorators directly with these constants instead of wrapper functions.

Example:
    from egregora.utils.retry import RETRYABLE_EXCEPTIONS, DEFAULT_RETRY_KWARGS
    from tenacity import retry

    @retry(**DEFAULT_RETRY_KWARGS)
    def my_function():
        ...
"""

from google.api_core import exceptions as google_exceptions
from google.genai import errors as genai_errors
from pydantic_ai.exceptions import UnexpectedModelBehavior
from tenacity import retry_if_exception_type, stop_after_attempt, wait_random_exponential

# Exceptions that should trigger a retry
RETRYABLE_EXCEPTIONS = (
    # PydanticAI exceptions
    UnexpectedModelBehavior,
    # Google API Core exceptions (used by google-genai and other Google APIs)
    google_exceptions.ResourceExhausted,
    google_exceptions.ServiceUnavailable,
    google_exceptions.InternalServerError,
    google_exceptions.GatewayTimeout,
    # google-genai v1 errors
    genai_errors.ServerError,
)

# Default retry configuration
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_MAX_DELAY = 10.0

# Pre-configured retry kwargs for common use cases
DEFAULT_RETRY_KWARGS = {
    "stop": stop_after_attempt(DEFAULT_MAX_ATTEMPTS),
    "wait": wait_random_exponential(multiplier=DEFAULT_INITIAL_DELAY, max=DEFAULT_MAX_DELAY),
    "retry": retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    "reraise": True,
}

# Aggressive retry for batch operations
BATCH_RETRY_KWARGS = {
    "stop": stop_after_attempt(5),
    "wait": wait_random_exponential(min=2.0, max=60.0),
    "retry": retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    "reraise": True,
}

__all__ = [
    "RETRYABLE_EXCEPTIONS",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_INITIAL_DELAY",
    "DEFAULT_MAX_DELAY",
    "DEFAULT_RETRY_KWARGS",
    "BATCH_RETRY_KWARGS",
]
