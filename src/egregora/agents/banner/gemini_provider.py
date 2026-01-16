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
    """Generate images using the Gemini Batch API."""

    def __init__(self, client: genai.GenerativeModel, model: str) -> None:
        self._client = client
        self._model = model
        self._poll_interval = 10.0
        self._timeout = 600.0  # 10 minutes for batch

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate image using a direct generation call."""
        try:
            response = self._client.generate_content(request.prompt)
            image_bytes = response.parts[0].inline_data.data
            mime_type = response.parts[0].inline_data.mime_type
            return ImageGenerationResult(image_bytes=image_bytes, mime_type=mime_type)
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return ImageGenerationResult(
                image_bytes=None, mime_type=None, error=str(e), error_code="GENERATION_FAILED"
            )
