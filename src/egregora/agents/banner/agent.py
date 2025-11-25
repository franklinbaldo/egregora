"""Pydantic-AI powered banner generation agent.

This module implements banner generation using a single multimodal model
(gemini-2.5-flash-image) that directly generates images from text prompts.

No separate "creative director" LLM - the image model handles both creative
interpretation and generation in a single API call.
"""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

from egregora.config import EgregoraConfig, google_api_key_status
from egregora.data_primitives.document import Document, DocumentType
from egregora.resources.prompts import render_prompt
from egregora.utils.retry import RetryPolicy, retry_sync

logger = logging.getLogger(__name__)

# Constants
_BANNER_ASPECT_RATIO = "16:9"
_RESPONSE_MODALITIES_IMAGE = "IMAGE"
_RESPONSE_MODALITIES_TEXT = "TEXT"


class BannerInput(BaseModel):
    """Input parameters for banner generation."""

    post_title: str = Field(description="Blog post title")
    post_summary: str = Field(description="Brief summary of the post")
    slug: str | None = Field(default=None, description="Post slug for metadata")
    language: str = Field(default="pt-BR", description="Content language")


class BannerOutput(BaseModel):
    """Output from banner generation.

    Contains a Document with binary image content. Filesystem operations
    (saving, paths, URLs) are handled by upper layers.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    document: Document | None = None
    error: str | None = None
    error_code: str | None = Field(
        default=None,
        description="Optional machine-readable error code for troubleshooting",
    )
    debug_text: str | None = Field(default=None, description="Debug text from model response")

    @property
    def success(self) -> bool:
        """True if a document was successfully generated."""
        return self.document is not None


def _build_image_prompt(input_data: BannerInput) -> str:
    """Build the image generation prompt from post metadata."""
    return render_prompt(
        "banner.jinja",
        post_title=input_data.post_title,
        post_summary=input_data.post_summary,
    )


def _generate_banner_image(
    client: genai.Client,
    input_data: BannerInput,
    image_model: str,
) -> BannerOutput:
    """Generate banner image using Gemini multimodal image model.

    Args:
        client: Gemini API client
        input_data: Banner generation parameters
        image_model: Model name

    Returns:
        BannerOutput with Document containing binary image data

    """
    prompt = _build_image_prompt(input_data)
    logger.info("Generating banner with %s for: %s", image_model, input_data.post_title)

    try:
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        generate_content_config = types.GenerateContentConfig(
            response_modalities=[_RESPONSE_MODALITIES_IMAGE, _RESPONSE_MODALITIES_TEXT],
            image_config=types.ImageConfig(aspect_ratio=_BANNER_ASPECT_RATIO),
        )

        # Call the image model
        stream = client.models.generate_content_stream(
            model=image_model, contents=contents, config=generate_content_config
        )

        # Extract image and optional debug text
        image_bytes: bytes | None = None
        mime_type: str = "image/png"
        debug_text_parts: list[str] = []

        for chunk in stream:
            if not chunk.candidates:
                continue

            for candidate in chunk.candidates:
                if not (candidate.content and candidate.content.parts):
                    continue

                for part in candidate.content.parts:
                    # Collect any text responses for debugging
                    text_part = getattr(part, "text", None)
                    if text_part:
                        debug_text_parts.append(text_part)

                    # Extract image data (first hit wins)
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and inline_data.data and image_bytes is None:
                        image_bytes = inline_data.data
                        mime_type = inline_data.mime_type

        if image_bytes is None:
            error_msg = "No image data received from API"
            logger.error("%s for post '%s'", error_msg, input_data.post_title)
            return BannerOutput(error=error_msg, error_code="NO_IMAGE_DATA")

        # Create Document with binary content
        document = Document(
            content=image_bytes,
            type=DocumentType.MEDIA,
            metadata={
                "mime_type": mime_type,
                "source": image_model,
                "slug": input_data.slug,
                "language": input_data.language,
            },
        )

        debug_text = "\n".join(debug_text_parts) if debug_text_parts else None
        if debug_text:
            logger.debug("Banner generation debug text: %s", debug_text)

        return BannerOutput(document=document, debug_text=debug_text)

    except Exception as e:
        logger.exception("Banner image generation failed for post '%s'", input_data.post_title)
        return BannerOutput(error=type(e).__name__, error_code="GENERATION_EXCEPTION")


def generate_banner(
    post_title: str,
    post_summary: str,
    slug: str | None = None,
    language: str = "pt-BR",
) -> BannerOutput:
    """Generate a banner image using the Gemini multimodal image model.

    This is a single-model approach: gemini-2.5-flash-image handles both
    creative interpretation and image generation in one API call.

    The function returns a Document with binary image content. Filesystem
    operations (saving to disk, URL generation) are handled by upper layers.

    Args:
        post_title: Title of the blog post
        post_summary: Summary of the post content
        slug: Optional post slug for metadata
        language: Content language (default: pt-BR)

    Returns:
        BannerOutput with Document containing binary image or error message

    Note:
        Requires GOOGLE_API_KEY environment variable to be set.

    """
    # Client reads GOOGLE_API_KEY from environment automatically
    client = genai.Client()

    # Load configuration
    config = EgregoraConfig()
    image_model = config.models.banner

    input_data = BannerInput(
        post_title=post_title,
        post_summary=post_summary,
        slug=slug,
        language=language,
    )

    # Retry policy for API resilience
    retry_policy = RetryPolicy()

    def _generate() -> BannerOutput:
        return _generate_banner_image(client, input_data, image_model)

    try:
        return retry_sync(_generate, retry_policy)
    except Exception as e:
        logger.exception("Banner generation failed after retries")
        return BannerOutput(error=type(e).__name__, error_code="RETRY_FAILED")


def is_banner_generation_available() -> bool:
    """Check if banner generation is available (GOOGLE_API_KEY is set).

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    """
    return google_api_key_status()
