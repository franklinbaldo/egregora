"""Tests for GeminiKeyRotator."""
import pytest
from egregora.llm.providers.model_cycler import GeminiKeyRotator

class TestGeminiKeyRotator:
    def test_exhaustion_behavior(self):
        """
        Verify if GeminiKeyRotator rotates correctly without exhaustion on success.
        """
        api_keys = ["key1", "key2"]
        rotator = GeminiKeyRotator(api_keys=api_keys)

        # Call 1 (Success)
        rotator.call_with_rotation(lambda k: "success")
        assert rotator.current_key == "key2"

        # Call 2 (Success)
        rotator.call_with_rotation(lambda k: "success")
        assert rotator.current_key == "key1" # Back to start (Round Robin)

        # Verify NO exhaustion error
        rotator.call_with_rotation(lambda k: "success")
        assert rotator.current_key == "key2"

    def test_exhaustion_on_failure(self):
        """Verify it DOES exhaust on rate limit."""
        api_keys = ["key1", "key2"]
        rotator = GeminiKeyRotator(api_keys=api_keys)

        def fail_first(key):
            if key == "key1":
                raise ValueError("429 Too Many Requests")
            return "success"

        # Call should succeed with key2
        res = rotator.call_with_rotation(fail_first)
        assert res == "success"

        # key1 should be exhausted
        assert "key1" in rotator._exhausted_keys
