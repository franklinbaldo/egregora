"""V3 Banner Generator using synchronous Gemini API.

This module implements a robust banner generator for Egregora V3,
replacing the fragile batch-based implementation in V2.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import types

from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)

if TYPE_CHECKING:
    from google.genai import Client

logger = logging.getLogger(__name__)


class GeminiV3BannerGenerator(ImageGenerationProvider):
    """V3-compliant Banner Generator using Google GenAI SDK.

    Uses the synchronous `models.generate_image` endpoint (or equivalent)
    instead of the complex Batch API.
    """

    def __init__(self, client: Client, model: str = "imagen-3.0-generate-001") -> None:
        """Initialize the generator.

        Args:
            client: Authenticated Google GenAI client.
            model: Model name to use (default: imagen-3.0-generate-001).
        """
        self._client = client
        self._model = model

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate an image from the request.

        Args:
            request: The generation request containing the prompt.

        Returns:
            ImageGenerationResult containing the image bytes or error.
        """
        logger.info("Generating banner with model %s", self._model)

        try:
            # Declaratively create config if aspect_ratio is present.
            config = (
                types.GenerateImagesConfig(aspect_ratio=request.aspect_ratio)
                if request.aspect_ratio
                else None
            )

            response = self._client.models.generate_images(
                model=self._model, prompt=request.prompt, config=config
            )

            # Extract image
            if not response.generated_images:
                return ImageGenerationResult(
                    image_bytes=None,
                    mime_type=None,
                    error="No images returned",
                    error_code="NO_IMAGE",
                )

            # Get the first image
            generated_image = response.generated_images[0]
            image_data = generated_image.image.image_bytes
            mime_type = generated_image.image.mime_type or "image/png"

            return ImageGenerationResult(image_bytes=image_data, mime_type=mime_type)

        except Exception as e:
            logger.exception("Banner generation failed")
            return ImageGenerationResult(
                image_bytes=None,
                mime_type=None,
                error=str(e),
                error_code="GENERATION_EXCEPTION",
            )
