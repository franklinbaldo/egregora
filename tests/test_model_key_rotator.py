"""Tests for ModelKeyRotator to verify proper key and model rotation."""

import logging

import pytest

from egregora.llm.providers.model_cycler import GeminiKeyRotator


def test_model_key_rotator_exhausts_keys_per_model():
    """Test that all keys are tried for each model before rotating models."""
    # Setup
    api_keys = ["key-a", "key-b", "key-c"]

    rotator = GeminiKeyRotator(api_keys=api_keys)

    call_log = []
    call_count = 0

    def mock_api_call(api_key: str) -> str:
        """Mock API call that fails with 429 for first 8 attempts."""
        nonlocal call_count
        call_log.append(api_key)
        call_count += 1

        # Fail first 2 calls
        if call_count <= 2:
            msg = "429 Too Many Requests"
            raise Exception(msg)

        # 3rd call succeeds
        return f"Success with {api_key}"

    # Execute
    result = rotator.call_with_rotation(mock_api_call)

    # Verify rotation order
    expected_order = [
        "key-a",
        "key-b",
        "key-c",
    ]

    assert call_log == expected_order, f"Expected {expected_order}, got {call_log}"
    assert result == "Success with key-c"


def test_model_key_rotator_fails_when_all_exhausted():
    """Test that rotator raises exception when all models+keys are exhausted."""
    api_keys = ["key-a", "key-b"]

    rotator = GeminiKeyRotator(api_keys=api_keys)

    def always_fails(api_key: str) -> str:
        msg = "429 Too Many Requests"
        raise RuntimeError(msg)

    # Should try all 2 keys then raise
    with pytest.raises(RuntimeError):
        rotator.call_with_rotation(always_fails)


def test_model_key_rotator_succeeds_on_first_try():
    """Test that rotator succeeds immediately if first call works."""
    api_keys = ["key-a", "key-b"]

    rotator = GeminiKeyRotator(api_keys=api_keys)

    call_log = []

    def succeeds_immediately(api_key: str) -> str:
        call_log.append(api_key)
        return "Success"

    result = rotator.call_with_rotation(succeeds_immediately)

    # Should only call once
    assert len(call_log) == 1
    assert call_log[0] == "key-a"
    assert result == "Success"


def test_key_rotator_handles_rate_limit_logging_without_attribute_error(caplog):
    """Ensure key rotation on rate limit does not raise AttributeError during logging."""
    api_keys = ["key-a", "key-b"]
    rotator = GeminiKeyRotator(api_keys=api_keys)

    call_log = []

    class RateLimitError(Exception):
        pass

    def fail_once_then_succeed(api_key: str) -> str:
        call_log.append(api_key)
        if len(call_log) == 1:
            raise RateLimitError("429 Too Many Requests")
        return "Success"

    with caplog.at_level(logging.WARNING):
        result = rotator.call_with_rotation(
            fail_once_then_succeed, is_rate_limit_error=lambda exc: isinstance(exc, RateLimitError)
        )

    assert result == "Success"
    # First key should hit rate limit and rotate to second key without AttributeError
    assert call_log == ["key-a", "key-b"]
    assert any("[KeyRotator] Rate limit on key index" in record.message for record in caplog.records)


if __name__ == "__main__":
    # Run tests

    try:
        test_model_key_rotator_exhausts_keys_per_model()
        test_model_key_rotator_succeeds_on_first_try()
        test_model_key_rotator_fails_when_all_exhausted()

    except AssertionError:
        raise
