"""Tests for ModelKeyRotator to verify proper key and model rotation."""

from egregora.models.model_key_rotator import ModelKeyRotator


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
            raise Exception("429 Too Many Requests")

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
    print("✓ ModelKeyRotator exhausts all keys per model before rotating")


def test_model_key_rotator_fails_when_all_exhausted():
    """Test that rotator raises exception when all models+keys are exhausted."""
    models = ["model-1", "model-2"]
    api_keys = ["key-a", "key-b"]

    rotator = ModelKeyRotator(models=models, api_keys=api_keys)

    def always_fails(model: str, api_key: str) -> str:
        raise Exception("429 Too Many Requests")

    # Should try all 4 combinations (2 models × 2 keys) then raise
    try:
        rotator.call_with_rotation(always_fails)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "429" in str(e)
        print("✓ ModelKeyRotator raises after exhausting all combinations")


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
    print("✓ ModelKeyRotator succeeds on first try without rotation")


if __name__ == "__main__":
    # Run tests
    print("\n=== Testing ModelKeyRotator ===\n")

    try:
        test_model_key_rotator_exhausts_keys_per_model()
        test_model_key_rotator_succeeds_on_first_try()
        test_model_key_rotator_fails_when_all_exhausted()

        print("\n✅ All tests passed!")
        print("\nRotation order verified:")
        print("  Model1+Key1 → Model1+Key2 → Model1+Key3 →")
        print("  Model2+Key1 → Model2+Key2 → Model2+Key3 →")
        print("  Model3+Key1 → etc.")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
