from __future__ import annotations

from httpx import HTTPError
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_core import ValidationError
from tenacity import retry_if_exception_type, stop_after_attempt, wait_random_exponential

from egregora.llm.retry import (
    RETRY_IF,
    RETRY_STOP,
    RETRY_WAIT,
    RETRYABLE_EXCEPTIONS,
)


def test_retry_constants_types():
    """Verify the types of the retry constants."""
    assert isinstance(RETRYABLE_EXCEPTIONS, tuple)
    assert isinstance(RETRY_STOP, stop_after_attempt)
    assert isinstance(RETRY_WAIT, wait_random_exponential)
    assert isinstance(RETRY_IF, retry_if_exception_type)


def test_retryable_exceptions():
    """Verify the content of the RETRYABLE_EXCEPTIONS tuple."""
    assert (
        UnexpectedModelBehavior,
        HTTPError,
        ValidationError,
    ) == RETRYABLE_EXCEPTIONS


def test_retry_stop_config():
    """Verify the configuration of the RETRY_STOP constant."""
    assert RETRY_STOP.max_attempt_number == 5


def test_retry_wait_config():
    """Verify the configuration of the RETRY_WAIT constant."""
    assert RETRY_WAIT.min == 2.0
    assert RETRY_WAIT.max == 60.0


def test_retry_if_config():
    """Verify the configuration of the RETRY_IF constant."""
    assert RETRY_IF.exception_types == RETRYABLE_EXCEPTIONS
