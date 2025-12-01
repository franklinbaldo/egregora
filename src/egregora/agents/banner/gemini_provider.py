"""Gemini implementation of the image generation abstraction."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import httpx
from google.genai import types as genai_types

from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from egregora.config.settings import get_google_api_key

logger = logging.getLogger(__name__)


class GeminiImageGenerationProvider(ImageGenerationProvider):
    """Generate images using the Gemini multimodal HTTP API."""

    def __init__(self, client: httpx.Client, model: str) -> None:
        self._client = client
        self._model = model

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        # If client exposes a models.generate_content_stream (used in tests), use it.
        if hasattr(self._client, "models"):
            return self._generate_via_stream(request)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
        payload: dict[str, object] = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": {},
        }
        if request.response_modalities:
            payload["responseModalities"] = list(request.response_modalities)
        if request.aspect_ratio:
            payload["generationConfig"]["aspectRatio"] = request.aspect_ratio

        api_key = get_google_api_key()
        response = self._client.post(url, params={"key": api_key}, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates") or []

        image_bytes: bytes | None = None
        mime_type: str | None = None
        debug_text_parts: list[str] = []

        for cand in candidates:
            for part in cand.get("content", {}).get("parts", []):
                if "text" in part:
                    debug_text_parts.append(part["text"])
                if "inlineData" in part and image_bytes is None:
                    inline = part["inlineData"]
                    data_field = inline.get("data")
                    if isinstance(data_field, str):
                        import base64

                        image_bytes = base64.b64decode(data_field)
                    else:
                        image_bytes = data_field
                    mime_type = inline.get("mimeType")

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

    def _generate_via_stream(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        contents = [genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=request.prompt)])]
        config = getattr(genai_types, "GenerateContentConfig", SimpleNamespace)()
        config.response_modalities = None
        config.image_config = None
        if request.response_modalities:
            config.response_modalities = list(request.response_modalities)
        if request.aspect_ratio:
            image_config_cls = getattr(genai_types, "ImageConfig", SimpleNamespace)
            config.image_config = image_config_cls(aspect_ratio=request.aspect_ratio)

        stream = self._client.models.generate_content_stream(
            model=self._model, contents=contents, config=config
        )

        image_bytes: bytes | None = None
        mime_type: str | None = None
        debug_text_parts: list[str] = []

        for chunk in stream:
            if not getattr(chunk, "candidates", None):
                continue
            for candidate in chunk.candidates:
                content = getattr(candidate, "content", None)
                if not content or not getattr(content, "parts", None):
                    continue
                for part in content.parts:
                    text_part = getattr(part, "text", None)
                    if text_part:
                        debug_text_parts.append(text_part)
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and getattr(inline_data, "data", None) and image_bytes is None:
                        image_bytes = inline_data.data
                        mime_type = getattr(inline_data, "mime_type", None)

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
