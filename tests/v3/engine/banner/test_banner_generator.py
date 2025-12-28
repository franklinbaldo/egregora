"""Tests for V3 Banner Generator."""
from unittest.mock import MagicMock, Mock, patch

import pytest
from google.genai import types

from egregora.agents.banner.image_generation import (
    ImageGenerationRequest,
    ImageGenerationResult,
)
from egregora_v3.engine.banner.generator import GeminiV3BannerGenerator


@pytest.fixture
def mock_genai_client() -> MagicMock:
    """Fixture for a mocked Google GenAI client."""
    return MagicMock()


@patch("egregora_v3.engine.banner.generator.logger")
def test_gemini_v3_banner_generator_with_aspect_ratio(
    mock_logger: MagicMock, mock_genai_client: MagicMock
):
    """Verify generator correctly handles request with aspect ratio."""
    # Setup
    generator = GeminiV3BannerGenerator(client=mock_genai_client)
    request = ImageGenerationRequest(
        prompt="A test prompt",
        aspect_ratio="SQUARE",
        response_modalities=["IMAGE"],
    )

    # Mock the response from the SDK
    mock_image = Mock()
    mock_image.image.image_bytes = b"test_image_bytes"
    mock_image.image.mime_type = "image/png"

    mock_response = Mock()
    mock_response.generated_images = [mock_image]
    mock_genai_client.models.generate_images.return_value = mock_response

    # Execute
    result = generator.generate(request)

    # Verify
    mock_genai_client.models.generate_images.assert_called_once()
    call_args, call_kwargs = mock_genai_client.models.generate_images.call_args
    assert call_kwargs["prompt"] == "A test prompt"
    assert isinstance(call_kwargs["config"], types.GenerateImagesConfig)
    assert call_kwargs["config"].aspect_ratio == "SQUARE"

    assert result.image_bytes == b"test_image_bytes"
    assert result.mime_type == "image/png"
    assert result.error is None
    mock_logger.info.assert_called_once()


def test_gemini_v3_banner_generator_without_aspect_ratio(
    mock_genai_client: MagicMock,
):
    """Verify generator correctly handles request without aspect ratio."""
    # Setup
    generator = GeminiV3BannerGenerator(client=mock_genai_client)
    request = ImageGenerationRequest(
        prompt="A test prompt", response_modalities=["IMAGE"]
    )

    # Mock the response
    mock_image = Mock()
    mock_image.image.image_bytes = b"test_image_bytes"
    mock_image.image.mime_type = "image/jpeg"

    mock_response = Mock()
    mock_response.generated_images = [mock_image]
    mock_genai_client.models.generate_images.return_value = mock_response

    # Execute
    result = generator.generate(request)

    # Verify
    mock_genai_client.models.generate_images.assert_called_once_with(
        model="imagen-3.0-generate-001",
        prompt="A test prompt",
        config=None,
    )
    assert result.image_bytes == b"test_image_bytes"
    assert result.mime_type == "image/jpeg"
    assert result.error is None


@patch("egregora_v3.engine.banner.generator.logger")
def test_gemini_v3_banner_generator_handles_api_exception(
    mock_logger: MagicMock, mock_genai_client: MagicMock
):
    """Verify generator returns an error result on API exception."""
    # Setup
    generator = GeminiV3BannerGenerator(client=mock_genai_client)
    request = ImageGenerationRequest(
        prompt="A test prompt", response_modalities=["IMAGE"]
    )
    mock_genai_client.models.generate_images.side_effect = ValueError("API Error")

    # Execute
    result = generator.generate(request)

    # Verify
    assert result.image_bytes is None
    assert result.error == "API Error"
    assert result.error_code == "GENERATION_EXCEPTION"
    mock_logger.error.assert_called_once()


def test_gemini_v3_banner_generator_handles_no_images_returned(
    mock_genai_client: MagicMock,
):
    """Verify generator returns an error if no images are in the response."""
    # Setup
    generator = GeminiV3BannerGenerator(client=mock_genai_client)
    request = ImageGenerationRequest(
        prompt="A test prompt", response_modalities=["IMAGE"]
    )

    mock_response = Mock()
    mock_response.generated_images = []
    mock_genai_client.models.generate_images.return_value = mock_response

    # Execute
    result = generator.generate(request)

    # Verify
    assert result.image_bytes is None
    assert result.error == "No images returned"
    assert result.error_code == "NO_IMAGE"


def test_gemini_v3_banner_generator_handles_no_mime_type(
    mock_genai_client: MagicMock,
):
    """Verify generator provides a default mime_type if missing from response."""
    # Setup
    generator = GeminiV3BannerGenerator(client=mock_genai_client)
    request = ImageGenerationRequest(
        prompt="A test prompt", response_modalities=["IMAGE"]
    )

    mock_image = Mock()
    mock_image.image.image_bytes = b"test_image_bytes"
    mock_image.image.mime_type = None  # Explicitly set to None

    mock_response = Mock()
    mock_response.generated_images = [mock_image]
    mock_genai_client.models.generate_images.return_value = mock_response

    # Execute
    result = generator.generate(request)

    # Verify
    assert result.image_bytes == b"test_image_bytes"
    assert result.mime_type == "image/png"  # Should fallback to default
    assert result.error is None
