"""Centralized retry configuration for LLM calls."""

from __future__ import annotations

from httpx import HTTPError
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_core import ValidationError
from tenacity import retry_if_exception_type, stop_after_attempt, wait_random_exponential

# Shared retry configuration
RETRYABLE_EXCEPTIONS = (UnexpectedModelBehavior, HTTPError, ValidationError)
RETRY_STOP = stop_after_attempt(5)
RETRY_WAIT = wait_random_exponential(min=2.0, max=60.0)
RETRY_IF = retry_if_exception_type(RETRYABLE_EXCEPTIONS)
