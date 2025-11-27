"""Gemini implementation of the image generation abstraction."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)

logger = logging.getLogger(__name__)


class GeminiImageGenerationProvider(ImageGenerationProvider):
    """Generate images using the Gemini multimodal API."""

    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:  # noqa: D401
        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=request.prompt)])
        ]

        config_kwargs: dict[str, object] = {}
        if request.response_modalities:
            config_kwargs["response_modalities"] = list(request.response_modalities)

        if request.aspect_ratio:
            config_kwargs["image_config"] = types.ImageConfig(
                aspect_ratio=request.aspect_ratio
            )

        generate_content_config = types.GenerateContentConfig(**config_kwargs)

        stream = self._client.models.generate_content_stream(
            model=self._model, contents=contents, config=generate_content_config
        )

        image_bytes: bytes | None = None
        mime_type: str | None = None
        debug_text_parts: list[str] = []

        for chunk in stream:
            if not chunk.candidates:
                continue

            for candidate in chunk.candidates:
                if not (candidate.content and candidate.content.parts):
                    continue

                for part in candidate.content.parts:
                    text_part = getattr(part, "text", None)
                    if text_part:
                        debug_text_parts.append(text_part)

                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and inline_data.data and image_bytes is None:
                        image_bytes = inline_data.data
                        mime_type = inline_data.mime_type

        debug_text = "\n".join(debug_text_parts) if debug_text_parts else None

        if image_bytes is None or mime_type is None:
            error_msg = "No image data received from API"
            logger.error(error_msg)
            return ImageGenerationResult(
                image_bytes=None,
                mime_type=None,
                debug_text=debug_text,
                error=error_msg,
                error_code="NO_IMAGE_DATA",
            )

        return ImageGenerationResult(
            image_bytes=image_bytes,
            mime_type=mime_type,
            debug_text=debug_text,
        )

