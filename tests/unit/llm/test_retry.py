from __future__ import annotations

from httpx import HTTPError
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_core import ValidationError
from tenacity import retry_if_exception_type, stop_after_attempt, wait_random_exponential

from egregora.llm import retry


def test_retry_configuration() -> None:
    """Tests that the retry configuration is set up correctly."""
    assert isinstance(retry.RETRY_STOP, stop_after_attempt)
    assert retry.RETRY_STOP.max_attempt_number == 5

    assert isinstance(retry.RETRY_WAIT, wait_random_exponential)
    assert retry.RETRY_WAIT.min == 2.0
    assert retry.RETRY_WAIT.max == 60.0

    assert isinstance(retry.RETRY_IF, retry_if_exception_type)
    assert (UnexpectedModelBehavior, HTTPError, ValidationError) == retry.RETRYABLE_EXCEPTIONS
