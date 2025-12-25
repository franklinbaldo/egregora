"""Tests for ModelKeyRotator to verify proper key and model rotation."""

import logging

from egregora.llm.providers.model_cycler import GeminiKeyRotator
from egregora.llm.providers.model_key_rotator import ModelKeyRotator


def test_model_key_rotator_exhausts_keys_per_model():
    """Test that all keys are tried for each model before rotating models."""
    # Setup
    models = ["model-1", "model-2", "model-3"]
    api_keys = ["key-a", "key-b", "key-c"]

    rotator = ModelKeyRotator(models=models, api_keys=api_keys)

    call_log = []
    call_count = 0

    def mock_api_call(model: str, api_key: str) -> str:
        """Mock API call that fails with 429 for first 8 attempts."""
        nonlocal call_count
        call_log.append((model, api_key))
        call_count += 1

        # Fail first 8 calls (model-1: 3 keys, model-2: 3 keys, model-3: 2 keys)
        if call_count <= 8:
            msg = "429 Too Many Requests"
            raise Exception(msg)

        # 9th call succeeds
        return f"Success with {model} and {api_key}"

    # Execute
    result = rotator.call_with_rotation(mock_api_call)

    # Verify rotation order
    expected_order = [
        # Model 1 tries all keys
        ("model-1", "key-a"),
        ("model-1", "key-b"),
        ("model-1", "key-c"),
        # Model 2 tries all keys
        ("model-2", "key-a"),
        ("model-2", "key-b"),
        ("model-2", "key-c"),
        # Model 3 tries keys until success
        ("model-3", "key-a"),
        ("model-3", "key-b"),
        ("model-3", "key-c"),  # This one succeeds
    ]

    assert call_log == expected_order, f"Expected {expected_order}, got {call_log}"
    assert result == "Success with model-3 and key-c"


def test_model_key_rotator_fails_when_all_exhausted():
    """Test that rotator raises exception when all models+keys are exhausted."""
    models = ["model-1", "model-2"]
    api_keys = ["key-a", "key-b"]

    rotator = ModelKeyRotator(models=models, api_keys=api_keys)

    def always_fails(model: str, api_key: str) -> str:
        msg = "429 Too Many Requests"
        raise RuntimeError(msg)

    # Should try all 4 combinations (2 models x 2 keys) then raise
    try:
        rotator.call_with_rotation(always_fails)
        msg = "Should have raised exception"
        raise AssertionError(msg)
    except RuntimeError as exc:
        assert "429" in str(exc)


def test_model_key_rotator_succeeds_on_first_try():
    """Test that rotator succeeds immediately if first call works."""
    models = ["model-1", "model-2"]
    api_keys = ["key-a", "key-b"]

    rotator = ModelKeyRotator(models=models, api_keys=api_keys)

    call_log = []

    def succeeds_immediately(model: str, api_key: str) -> str:
        call_log.append((model, api_key))
        return "Success"

    result = rotator.call_with_rotation(succeeds_immediately)

    # Should only call once
    assert len(call_log) == 1
    assert call_log[0] == ("model-1", "key-a")
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
    assert any(
        "[KeyRotator] Rate limit on key index" in record.message for record in caplog.records
    )


if __name__ == "__main__":
    # Run tests

    try:
        test_model_key_rotator_exhausts_keys_per_model()
        test_model_key_rotator_succeeds_on_first_try()
        test_model_key_rotator_fails_when_all_exhausted()

    except AssertionError:
        raise
