"""V3 Banner Generator using synchronous Gemini API.

This module implements a robust banner generator for Egregora V3.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from google.genai import types

from egregora.agents.banner.image_generation import (
    ImageGenerationRequest,
    ImageGenerationResult,
)

if TYPE_CHECKING:
    from google.genai import Client

logger = logging.getLogger(__name__)


def generate_image_with_gemini(
    client: Client,
    request: ImageGenerationRequest,
    model: str = "models/gemini-1.5-flash-latest",
) -> ImageGenerationResult:
    """Generate an image from the request using the Gemini API.

    Args:
        client: Authenticated Google GenAI client.
        request: The generation request containing the prompt.
        model: Model name to use (default: models/gemini-1.5-flash-latest).

    Returns:
        ImageGenerationResult containing the image bytes or error.
    """
    logger.info("Generating banner with model %s", model)

    # Prepare configuration declaratively
    config_params = {"aspect_ratio": request.aspect_ratio} if request.aspect_ratio else {}

    try:
        response = client.models.generate_images(
            model=model,
            prompt=request.prompt,
            config=(
                types.GenerateImagesConfig(**config_params)
                if config_params
                else None
            ),
        )
    except Exception as e:
        logger.error("Gemini image generation failed: %s", e, exc_info=True)
        return ImageGenerationResult(
            image_bytes=None,
            mime_type=None,
            error="API Error",
            error_code="GENERATION_EXCEPTION",
        )

    if not response.generated_images:
        return ImageGenerationResult(
            image_bytes=None,
            mime_type=None,
            error="No images returned",
            error_code="NO_IMAGE",
        )

    generated_image = response.generated_images[0]
    image_data = generated_image.image.image_bytes
    mime_type = generated_image.image.mime_type or "image/png"

    return ImageGenerationResult(image_bytes=image_data, mime_type=mime_type)
