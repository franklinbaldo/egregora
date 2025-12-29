from unittest.mock import MagicMock, patch

from google.api_core import exceptions as google_exceptions

from egregora.agents.banner.agent import generate_banner, is_banner_generation_available
from egregora.agents.banner.image_generation import ImageGenerationResult


# Test for is_banner_generation_available
@patch("os.environ.get")
def test_is_banner_generation_available_when_key_is_set(mock_get_env):
    mock_get_env.return_value = "fake-key"
    assert is_banner_generation_available() is True


@patch("os.environ.get")
def test_is_banner_generation_available_when_key_is_not_set(mock_get_env):
    mock_get_env.return_value = None
    assert is_banner_generation_available() is False


@patch("egregora.agents.banner.agent.is_banner_generation_available", return_value=False)
def test_generate_banner_when_not_available(mock_is_available):
    """Test that generate_banner returns an error when the feature is not available."""
    # Act
    result = generate_banner("A Title", "A summary")

    # Assert
    assert result.success is False
    assert result.document is None
    assert "Banner generation is not available" in result.error
    assert result.error_code == "NOT_CONFIGURED"


# Test for generate_banner and its integration with _generate_banner_image
@patch("egregora.agents.banner.agent.is_banner_generation_available", return_value=True)
@patch("egregora.agents.banner.agent.GeminiImageGenerationProvider")
@patch("egregora.agents.banner.agent.genai.Client")
def test_generate_banner_success_with_debug_text(mock_client, mock_provider_cls, mock_is_available):
    """Test successful banner generation including debug text path."""
    # Arrange
    mock_provider_instance = MagicMock()
    mock_provider_cls.return_value = mock_provider_instance

    mock_result = ImageGenerationResult(
        image_bytes=b"image data",
        mime_type="image/png",
        debug_text="Some debug info",
    )
    mock_provider_instance.generate.return_value = mock_result

    # Act
    result = generate_banner("A Title", "A summary")

    # Assert
    assert result.success is True
    assert result.document is not None
    assert result.document.content == b"image data"
    assert result.debug_text == "Some debug info"


@patch("egregora.agents.banner.agent.is_banner_generation_available", return_value=True)
@patch("egregora.agents.banner.agent.GeminiImageGenerationProvider")
@patch("egregora.agents.banner.agent.genai.Client")
def test_generate_banner_failure_no_image_data(mock_client, mock_provider_cls, mock_is_available):
    """Test banner generation failure when provider returns no image."""
    # Arrange
    mock_provider_instance = MagicMock()
    mock_provider_cls.return_value = mock_provider_instance

    mock_result = ImageGenerationResult(
        image_bytes=None,
        mime_type=None,
        error="No image generated",
        error_code="NO_IMAGE",
        debug_text="Some debug info",
    )
    mock_provider_instance.generate.return_value = mock_result

    # Act
    result = generate_banner("A Title", "A summary")

    # Assert
    assert result.success is False
    assert result.document is None
    assert result.error == "No image generated"
    assert result.error_code == "NO_IMAGE"


@patch("egregora.agents.banner.agent.is_banner_generation_available", return_value=True)
@patch("egregora.agents.banner.agent.GeminiImageGenerationProvider")
@patch("egregora.agents.banner.agent.genai.Client")
def test_generate_banner_handles_google_api_call_error(mock_client, mock_provider_cls, mock_is_available):
    """Test that GoogleAPICallError during generation is handled gracefully."""
    # Arrange
    mock_provider_instance = MagicMock()
    mock_provider_cls.return_value = mock_provider_instance
    mock_provider_instance.generate.side_effect = google_exceptions.GoogleAPICallError("API error")

    # Act
    result = generate_banner("A Title", "A summary")

    # Assert
    assert result.success is False
    assert result.document is None
    assert result.error == "GoogleAPICallError"
    assert result.error_code == "GENERATION_EXCEPTION"
