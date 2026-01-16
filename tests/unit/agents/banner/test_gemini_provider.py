from unittest.mock import MagicMock

from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest


def test_gemini_provider_returns_image_and_debug_text():
    # Mock successful response
    img_data = b"img-bytes"

    mock_response = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = img_data
    mock_part.inline_data.mime_type = "image/png"

    mock_response.parts = [mock_part]

    mock_client = MagicMock()
    mock_client.generate_content.return_value = mock_response

    provider = GeminiImageGenerationProvider(client=mock_client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(
            prompt="banner prompt",
            response_modalities=["IMAGE"],
            aspect_ratio="4:3",
        )
    )

    assert result.image_bytes == img_data
    assert result.mime_type == "image/png"


def test_gemini_provider_returns_error_on_exception():
    mock_client = MagicMock()
    mock_client.generate_content.side_effect = Exception("API Error")

    provider = GeminiImageGenerationProvider(client=mock_client, model="models/test")

    result = provider.generate(
        ImageGenerationRequest(prompt="prompt", response_modalities=["IMAGE"], aspect_ratio=None)
    )

    assert not result.has_image
    assert result.error == "API Error"
    assert result.error_code == "GENERATION_FAILED"
