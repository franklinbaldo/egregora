from unittest.mock import MagicMock

from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest


def test_gemini_provider_returns_image():
    # Setup
    mock_client = MagicMock()
    mock_response = MagicMock()

    # Mock response structure: response.parts[0].inline_data.data / mime_type
    mock_part = MagicMock()
    mock_part.inline_data.data = b"image_data"
    mock_part.inline_data.mime_type = "image/png"

    mock_response.parts = [mock_part]
    mock_client.generate_content.return_value = mock_response

    provider = GeminiImageGenerationProvider(client=mock_client, model="models/test")

    # Act
    result = provider.generate(
        ImageGenerationRequest(
            prompt="banner prompt",
            response_modalities=["IMAGE"],
            aspect_ratio="4:3",
        )
    )

    # Assert
    assert result.has_image
    assert result.image_bytes == b"image_data"
    assert result.mime_type == "image/png"
    assert result.error is None

    mock_client.generate_content.assert_called_once_with("banner prompt")


def test_gemini_provider_returns_error_on_exception():
    # Setup
    mock_client = MagicMock()
    mock_client.generate_content.side_effect = Exception("API Error")

    provider = GeminiImageGenerationProvider(client=mock_client, model="models/test")

    # Act
    result = provider.generate(ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"]))

    # Assert
    assert not result.has_image
    assert result.error == "API Error"
    assert result.error_code == "GENERATION_FAILED"
