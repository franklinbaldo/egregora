import pytest

pytest.skip("rotating_fallback module removed - tests are stale", allow_module_level=True)

from unittest.mock import AsyncMock, MagicMock

from egregora.llm.providers.rotating_fallback import RotatingFallbackModel
from pydantic_ai.exceptions import ModelHTTPError

from egregora.llm.exceptions import AllModelsExhaustedError, InvalidConfigurationError


# A custom error to prove we are not relying on string matching
class SentinelError(Exception):
    pass


@pytest.mark.asyncio
async def test_rotating_fallback_retries_on_http_error():
    """RotatingFallbackModel should try each model in sequence on HTTP errors."""
    # Arrange
    failing_model1 = AsyncMock()
    failing_model1.request.side_effect = ModelHTTPError(500, "model1", "Internal Server Error")

    failing_model2 = AsyncMock()
    failing_model2.request.side_effect = ModelHTTPError(503, "model2", "Service Unavailable")

    succeeding_model = AsyncMock()
    expected_response = MagicMock()
    succeeding_model.request.return_value = expected_response

    # Create rotating provider with 3 models
    provider = RotatingFallbackModel(models=[failing_model1, failing_model2, succeeding_model])

    # Act
    result = await provider.request([], None, None)

    # Assert
    assert result == expected_response
    assert failing_model1.request.call_count == 1
    assert failing_model2.request.call_count == 1
    assert succeeding_model.request.call_count == 1


@pytest.mark.asyncio
async def test_rotating_fallback_raises_all_models_exhausted_when_all_fail():
    """RotatingFallbackModel should raise AllModelsExhaustedError if all models fail."""
    # Arrange
    failing_model1 = AsyncMock()
    failing_model1.request.side_effect = ModelHTTPError(500, "model1", "Error 1")

    failing_model2 = AsyncMock()
    failing_model2.request.side_effect = ModelHTTPError(503, "model2", "Error 2")

    provider = RotatingFallbackModel(models=[failing_model1, failing_model2])

    # Act & Assert
    with pytest.raises(AllModelsExhaustedError) as exc_info:
        await provider.request([], None, None)

    assert "All 2 models failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_rotating_fallback_propagates_non_http_errors():
    """RotatingFallbackModel should propagate non-HTTP errors immediately."""
    # Arrange
    failing_model = AsyncMock()
    failing_model.request.side_effect = SentinelError("Non-HTTP error")

    provider = RotatingFallbackModel(models=[failing_model])

    # Act & Assert
    with pytest.raises(SentinelError, match="Non-HTTP error"):
        await provider.request([], None, None)

    # Only one call should have been made (no fallback)
    assert failing_model.request.call_count == 1


@pytest.mark.asyncio
async def test_rotating_fallback_requires_at_least_one_model():
    """RotatingFallbackModel should raise InvalidConfigurationError if no models provided."""
    with pytest.raises(InvalidConfigurationError, match="At least one model must be provided"):
        RotatingFallbackModel(models=[])
