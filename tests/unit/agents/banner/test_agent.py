from unittest.mock import MagicMock, patch

from google.genai import errors as google_exceptions

from egregora.agents.banner.agent import generate_banner, is_banner_generation_available
from egregora.agents.banner.image_generation import ImageGenerationResult


# Test for is_banner_generation_available
@patch("os.environ.get")
def test_is_banner_generation_available_when_key_is_set(mock_get_env):
    def side_effect(key, _default=None):
        if key == "GOOGLE_API_KEY":
            return "fake-key"
        if key == "EGREGORA_SKIP_API_KEY_VALIDATION":
            return ""  # Ensure it's a string to avoid AttributeError
        return None

    mock_get_env.side_effect = side_effect
    assert is_banner_generation_available() is True


@patch("os.environ.get")
def test_is_banner_generation_available_when_key_is_not_set(mock_get_env):
    def side_effect(key, _default=None):
        if key == "EGREGORA_SKIP_API_KEY_VALIDATION":
            return ""  # Ensure it's a string to avoid AttributeError
        return None

    mock_get_env.side_effect = side_effect
    assert is_banner_generation_available() is False


@patch("os.environ.get")
def test_is_banner_generation_available_when_skip_validation_is_set(mock_get_env):
    def side_effect(key, _default=None):
        if key == "EGREGORA_SKIP_API_KEY_VALIDATION":
            return "true"
        return None

    mock_get_env.side_effect = side_effect
    assert is_banner_generation_available() is True


def test_generate_banner_when_not_available():
    """Test that generate_banner returns an error when the feature is not available."""
    with patch("egregora.agents.banner.agent.is_banner_generation_available", return_value=False):
        result = generate_banner("A Title", "A summary")

    assert result.success is False
    assert result.document is None
    assert "Banner generation is not available" in result.error
    assert result.error_code == "NOT_CONFIGURED"


# Test for generate_banner and its integration with _generate_banner_image
def test_generate_banner_success_with_debug_text():
    """Test successful banner generation including debug text path."""
    with (
        patch("egregora.agents.banner.agent.is_banner_generation_available", return_value=True),
        patch.dict("os.environ", {"GOOGLE_API_KEY": "dummy-key"}),
        patch("egregora.agents.banner.agent.GeminiImageGenerationProvider") as mock_provider_cls,
        patch("egregora.agents.banner.agent.genai.Client"),
    ):
        mock_provider_instance = MagicMock()
        mock_provider_cls.return_value = mock_provider_instance

        mock_result = ImageGenerationResult(
            image_bytes=b"image data",
            mime_type="image/png",
            debug_text="Some debug info",
        )
        mock_provider_instance.generate.return_value = mock_result

        result = generate_banner("A Title", "A summary")

    assert result.success is True
    assert result.document is not None
    assert result.document.content == b"image data"
    assert result.debug_text == "Some debug info"


def test_generate_banner_failure_no_image_data():
    """Test banner generation failure when provider returns no image."""
    with (
        patch("egregora.agents.banner.agent.is_banner_generation_available", return_value=True),
        patch.dict("os.environ", {"GOOGLE_API_KEY": "dummy-key"}),
        patch("egregora.agents.banner.agent.GeminiImageGenerationProvider") as mock_provider_cls,
        patch("egregora.agents.banner.agent.genai.Client"),
    ):
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

        result = generate_banner("A Title", "A summary")

    assert result.success is False
    assert result.document is None
    assert result.error == "No image generated"
    assert result.error_code == "NO_IMAGE"


def test_generate_banner_handles_google_api_call_error():
    """Test that GoogleAPICallError during generation is handled gracefully."""
    with (
        patch("egregora.agents.banner.agent.is_banner_generation_available", return_value=True),
        patch.dict("os.environ", {"GOOGLE_API_KEY": "dummy-key"}),
        patch("egregora.agents.banner.agent.GeminiImageGenerationProvider") as mock_provider_cls,
        patch("egregora.agents.banner.agent.genai.Client"),
    ):
        mock_provider_instance = MagicMock()
        mock_provider_cls.return_value = mock_provider_instance
        mock_provider_instance.generate.side_effect = google_exceptions.APIError(
            "API error", response_json={}
        )

        result = generate_banner("A Title", "A summary")

    assert result.success is False
    assert result.document is None
    assert result.error == "APIError"
    assert result.error_code == "GENERATION_EXCEPTION"
