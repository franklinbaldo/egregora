import os
from unittest.mock import MagicMock, patch

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


def test_create_writer_model_raises_error_on_missing_google_api_key(
    mock_config: EgregoraConfig, mock_context: MagicMock
):
    """Test that create_writer_model raises ValueError when Google API key is missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match=r"A Google model is configured, but no API key was found\."):
            create_writer_model(mock_config, mock_context, "test prompt")


@patch("egregora.agents.writer_setup.validate_prompt_fits")
@patch("egregora.agents.writer_setup.infer_model")
def test_create_writer_model_success_with_google_api_key(
    mock_infer_model: MagicMock,
    mock_validate_prompt: MagicMock,
    mock_config: EgregoraConfig,
    mock_context: MagicMock,
):
    """Test that create_writer_model succeeds when Google API key is present."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}, clear=True):
        model_instance = MagicMock()
        mock_infer_model.return_value = model_instance

        model = create_writer_model(mock_config, mock_context, "test prompt")

        mock_infer_model.assert_called_once_with("google-gla:gemini-test")
        mock_validate_prompt.assert_called_once_with(
            "test prompt",
            "google-gla:gemini-test",
            mock_config,
            mock_context.window_label,
            model_instance=model_instance,
        )
        assert model == model_instance


def test_create_writer_model_returns_test_model_if_provided(
    mock_config: EgregoraConfig, mock_context: MagicMock
):
    """Test that create_writer_model returns the test_model directly if it is provided."""
    test_model = MagicMock()
    model = create_writer_model(mock_config, mock_context, "test prompt", test_model=test_model)
    assert model == test_model
