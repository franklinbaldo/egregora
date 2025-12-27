
from unittest.mock import AsyncMock, MagicMock

import pytest
from egregora.llm.providers.rotating_fallback import RotatingFallbackModel
from pydantic_ai.exceptions import ModelHTTPError

from egregora.llm.exceptions import AllModelsExhaustedError, InvalidConfigurationError


# A custom error to prove we are not relying on string matching
class CustomRateLimitError(ModelHTTPError):
    def __init__(self, message: str, status_code: int = 429) -> None:
        super().__init__(model_name="test_model", body={"error": message}, status_code=status_code)

    def __str__(self) -> str:
        # Override to ensure "429" is NOT in the string representation
        return f"CustomRateLimitError: {self.body}"


@pytest.fixture
def mock_models():
    """Fixture to create a list of mock models."""
    return [MagicMock(request=AsyncMock()) for _ in range(3)]


def test_init_raises_for_mismatched_lengths():
    """
    RED: This test should fail because the current implementation raises a
    generic ValueError instead of the structured InvalidConfigurationError.
    """
    models = [MagicMock()]
    model_keys = ["key1", "key2"]  # Mismatched length
    with pytest.raises(InvalidConfigurationError):
        RotatingFallbackModel(models=models, model_keys=model_keys)


@pytest.mark.asyncio
async def test_request_raises_all_models_exhausted_on_persistent_failure(mock_models):
    """
    RED: This test should fail because the current implementation re-raises the last
    exception or a generic RuntimeError, not the structured AllModelsExhaustedError.
    It also proves the need to move away from string matching by using a custom error.
    """
    # Simulate persistent failures across all models
    # The first model will raise a custom error to test type checking vs. string matching
    mock_models[0].request.side_effect = CustomRateLimitError("Custom rate limit hit")
    mock_models[1].request.side_effect = ModelHTTPError(status_code=429, model_name="m1", body={})
    mock_models[2].request.side_effect = ModelHTTPError(status_code=500, model_name="m2", body={})

    model = RotatingFallbackModel(models=mock_models)

    with pytest.raises(AllModelsExhaustedError) as exc_info:
        await model.request(messages=[], model_settings=None, model_request_parameters=None)

    # Assert that the structured exception contains the underlying causes
    assert len(exc_info.value.causes) >= 3
    assert isinstance(exc_info.value.causes[0], CustomRateLimitError)
    assert isinstance(exc_info.value.causes[1], ModelHTTPError)
    assert isinstance(exc_info.value.causes[2], ModelHTTPError)
