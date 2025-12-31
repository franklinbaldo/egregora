import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from egregora.agents.writer_setup import create_writer_model
from egregora.config.settings import EgregoraConfig


@pytest.fixture
def mock_config(config_factory) -> EgregoraConfig:
    """Fixture for a mock EgregoraConfig."""
    config = config_factory()
    config.models.writer = "google-gla:gemini-test"
    return config


@pytest.fixture
def mock_context() -> MagicMock:
    """Fixture for a mock WriterDeps."""
    return MagicMock()


@pytest.mark.asyncio
async def test_create_writer_model_raises_error_on_missing_google_api_key(
    mock_config: EgregoraConfig, mock_context: MagicMock
):
    """Test that create_writer_model raises ValueError when Google API key is missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match=r"A Google model is configured, but no API key was found\."):
            await create_writer_model(mock_config, mock_context, "test prompt")


@pytest.mark.asyncio
@patch("egregora.agents.writer_setup.validate_prompt_fits", new_callable=AsyncMock)
@patch("pydantic_ai.models.google.GoogleModel")
async def test_create_writer_model_success_with_google_api_key(
    mock_google_model: MagicMock,
    mock_validate_prompt: AsyncMock,
    mock_config: EgregoraConfig,
    mock_context: MagicMock,
):
    """Test that create_writer_model succeeds when Google API key is present."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}, clear=True):
        model_instance = MagicMock()
        mock_google_model.return_value = model_instance

        model = await create_writer_model(mock_config, mock_context, "test prompt")

        mock_google_model.assert_called_once_with(api_key=None, model_name="gemini-test", streaming=True)
        mock_validate_prompt.assert_awaited_once()
        assert model == model_instance
