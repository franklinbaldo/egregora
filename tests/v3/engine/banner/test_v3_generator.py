
import unittest
from unittest.mock import MagicMock

from google.genai.types import GenerateImagesResponse, Image, GeneratedImage

from egregora.agents.banner.image_generation import (
    ImageGenerationRequest,
    ImageGenerationResult,
)
from egregora_v3.engine.banner.generator import generate_image_with_gemini


class TestGenerator(unittest.TestCase):
    def test_generate_image_with_gemini_success(self):
        # Arrange
        mock_client = MagicMock()
        mock_image_data = Image(image_bytes=b"test_image_bytes", mime_type="image/png")
        # The response contains a list of `GeneratedImage`, not `Image`
        mock_generated_image = GeneratedImage(image=mock_image_data)
        mock_response = GenerateImagesResponse(generated_images=[mock_generated_image])
        mock_client.models.generate_images.return_value = mock_response

        request = ImageGenerationRequest(
            prompt="test prompt",
            response_modalities=["IMAGE"],
            aspect_ratio="1:1",
        )

        # Act
        result = generate_image_with_gemini(mock_client, request)

        # Assert
        self.assertIsInstance(result, ImageGenerationResult)
        self.assertEqual(result.image_bytes, b"test_image_bytes")
        self.assertEqual(result.mime_type, "image/png")
        self.assertIsNone(result.error)
        mock_client.models.generate_images.assert_called_once()

    def test_generate_image_with_gemini_api_error(self):
        # Arrange
        mock_client = MagicMock()
        mock_client.models.generate_images.side_effect = Exception("API Error")

        request = ImageGenerationRequest(
            prompt="test prompt",
            response_modalities=["IMAGE"],
            aspect_ratio="1:1",
        )

        # Act
        result = generate_image_with_gemini(mock_client, request)

        # Assert
        self.assertIsInstance(result, ImageGenerationResult)
        self.assertIsNone(result.image_bytes)
        self.assertEqual(result.error, "API Error")
        self.assertEqual(result.error_code, "GENERATION_EXCEPTION")
        mock_client.models.generate_images.assert_called_once()

    def test_generate_image_with_gemini_no_image_returned(self):
        # Arrange
        mock_client = MagicMock()
        mock_response = GenerateImagesResponse(generated_images=[])
        mock_client.models.generate_images.return_value = mock_response

        request = ImageGenerationRequest(
            prompt="test prompt",
            response_modalities=["IMAGE"],
            aspect_ratio="1:1",
        )

        # Act
        result = generate_image_with_gemini(mock_client, request)

        # Assert
        self.assertIsInstance(result, ImageGenerationResult)
        self.assertIsNone(result.image_bytes)
        self.assertEqual(result.error, "No images returned")
        self.assertEqual(result.error_code, "NO_IMAGE")
        mock_client.models.generate_images.assert_called_once()
