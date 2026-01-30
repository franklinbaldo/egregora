from unittest.mock import Mock

import pytest

from egregora.llm.exceptions import AllApiKeysExhaustedError, AllModelsExhaustedError
from egregora.llm.providers.model_cycler import GeminiKeyRotator, GeminiModelCycler


class RateLimitError(Exception):
    pass


def is_rate_limit_error(exc):
    return isinstance(exc, RateLimitError)


class TestGeminiKeyRotator:
    def test_call_with_rotation_raises_specific_error_when_exhausted(self):
        """Verify behavior: raises AllApiKeysExhaustedError when all keys fail."""
        rotator = GeminiKeyRotator(api_keys=["key1", "key2"])

        # Mock function that always fails with RateLimitError
        mock_call = Mock(side_effect=RateLimitError("Quota exceeded"))

        with pytest.raises(AllApiKeysExhaustedError, match="All API keys exhausted") as exc_info:
            rotator.call_with_rotation(mock_call, is_rate_limit_error=is_rate_limit_error)

        assert mock_call.call_count == 2
        # Verify cause chaining
        assert isinstance(exc_info.value.__cause__, RateLimitError)


class TestGeminiModelCycler:
    def test_call_with_rotation_raises_specific_error_when_exhausted(self):
        """Verify behavior: raises AllModelsExhaustedError when all models fail."""
        cycler = GeminiModelCycler(models=["model1", "model2"])

        # Mock function that always fails with RateLimitError
        mock_call = Mock(side_effect=RateLimitError("Quota exceeded"))

        with pytest.raises(AllModelsExhaustedError, match="All models rate-limited") as exc_info:
            cycler.call_with_rotation(mock_call, is_rate_limit_error=is_rate_limit_error)

        assert mock_call.call_count == 2
        # Verify causes list
        assert len(exc_info.value.causes) == 2
        assert isinstance(exc_info.value.__cause__, RateLimitError)
