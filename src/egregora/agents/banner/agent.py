"""Pydantic-AI powered banner generation agent.

This module implements banner generation using a single multimodal model
(gemini-2.5-flash-image) that directly generates images from text prompts.

No separate "creative director" LLM - the image model handles both creative
interpretation and generation in a single API call.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

from egregora.data_primitives.document import Document, DocumentType
from egregora.utils.retry import RetryPolicy, retry_sync

logger = logging.getLogger(__name__)

# Constants
_DEFAULT_IMAGE_MODEL = "models/gemini-2.5-flash-image"
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
    debug_text: str | None = Field(default=None, description="Debug text from model response")

    @property
    def success(self) -> bool:
        """True if a document was successfully generated."""
        return self.document is not None


def _build_image_prompt(input_data: BannerInput) -> str:
    """Build the image generation prompt from post metadata.

    This prompt combines creative direction with post context in a single
    instruction for the multimodal image model.
    """
    return f"""Generate a striking, minimalist blog banner image for this post:

Title: {input_data.post_title}
Summary: {input_data.post_summary}

Design Requirements:
- Style: Abstract, conceptual, minimalist modern editorial
- Composition: Keep the UPPER 30% relatively clean for potential text overlay
- Focus: Main visual interest in the LOWER 2/3
- Colors: Bold but harmonious (2-4 colors maximum)
- NO text or typography in the image itself
- NO photorealism or complex details
- Use geometric forms, gradients, and symbolic elements

Think like an artist creating a visual metaphor, not a photographer capturing a scene.
The image should capture the essence of the article without literal depictions.
"""


def _generate_banner_image(
    client: genai.Client,
    input_data: BannerInput,
    image_model: str = _DEFAULT_IMAGE_MODEL,
) -> BannerOutput:
    """Generate banner image using Gemini multimodal image model.

    Args:
        client: Gemini API client
        input_data: Banner generation parameters
        image_model: Model name (defaults to gemini-2.5-flash-image)

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
            if not (chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts):
                continue

            for part in chunk.candidates[0].content.parts:
                # Collect any text responses for debugging
                if hasattr(part, "text") and part.text:
                    debug_text_parts.append(part.text)

                # Extract image data
                if part.inline_data and part.inline_data.data:
                    inline_data = part.inline_data
                    image_bytes = inline_data.data
                    mime_type = inline_data.mime_type

        if image_bytes is None:
            error_msg = "No image data received from API"
            logger.error(error_msg)
            return BannerOutput(error=error_msg)

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
        logger.exception("Banner image generation failed")
        return BannerOutput(error=str(e))


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

    input_data = BannerInput(
        post_title=post_title,
        post_summary=post_summary,
        slug=slug,
        language=language,
    )

    # Retry policy for API resilience
    retry_policy = RetryPolicy()

    def _generate() -> BannerOutput:
        return _generate_banner_image(client, input_data)

    try:
        return retry_sync(_generate, retry_policy)
    except Exception as e:
        logger.exception("Banner generation failed after retries")
        return BannerOutput(error=str(e))
