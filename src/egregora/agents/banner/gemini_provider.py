"""Gemini implementation of the image generation abstraction."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)

if TYPE_CHECKING:
    from google import genai

logger = logging.getLogger(__name__)


class GeminiImageGenerationProvider(ImageGenerationProvider):
    """Generate images using the Gemini API."""

    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate image using a direct generation call."""
        try:
            # New SDK structure: client.models.generate_content
            response = self._client.models.generate_content(
                model=self._model,
                contents=request.prompt,
                config={
                    "response_modalities": request.response_modalities,
                },
            )

            # Extract image from response parts
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    return ImageGenerationResult(
                        image_bytes=part.inline_data.data, mime_type=part.inline_data.mime_type
                    )

            return ImageGenerationResult(
                image_bytes=None,
                mime_type=None,
                error="No image data found in response",
                error_code="NO_IMAGE_DATA",
            )
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return ImageGenerationResult(
                image_bytes=None, mime_type=None, error=str(e), error_code="GENERATION_FAILED"
            )
