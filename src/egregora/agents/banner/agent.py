"""Pydantic-AI powered banner generation agent.

This module implements banner generation using a single multimodal model
(gemini-2.5-flash-image) that directly generates images from text prompts.

No separate "creative director" LLM - the image model handles both creative
interpretation and generation in a single API call.
"""

from __future__ import annotations

import logging

from google import genai
from pydantic import BaseModel, ConfigDict, Field

from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest
from egregora.config import EgregoraConfig, google_api_key_status
from egregora.data_primitives.document import Document, DocumentType
from egregora.resources.prompts import render_prompt
from egregora.utils.retry import retry_sync

logger = logging.getLogger(__name__)

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
    generation_request: ImageGenerationRequest,
) -> BannerOutput:
    """Generate banner image using Gemini multimodal image model."""
    logger.info("Generating banner with %s for: %s", image_model, input_data.post_title)

    try:
        provider = GeminiImageGenerationProvider(client=client, model=image_model)
        result = provider.generate(generation_request)

        if not result.has_image:
            error_message = result.error or "Image generation returned no data"
            logger.error("%s for post '%s'", error_message, input_data.post_title)
            return BannerOutput(error=error_message, error_code=result.error_code)

        # Create Document with binary content
        document = Document(
            content=result.image_bytes,
            type=DocumentType.MEDIA,
            metadata={
                "mime_type": result.mime_type,
                "source": image_model,
                "slug": input_data.slug,
                "language": input_data.language,
            },
        )

        if result.debug_text:
            logger.debug("Banner generation debug text: %s", result.debug_text)

        return BannerOutput(document=document, debug_text=result.debug_text)

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
    prompt = _build_image_prompt(input_data)

    def _generate() -> BannerOutput:
        generation_request = ImageGenerationRequest(
            prompt=prompt,
            response_modalities=config.image_generation.response_modalities,
            aspect_ratio=config.image_generation.aspect_ratio,
        )
        return _generate_banner_image(client, input_data, image_model, generation_request)

    try:
        return retry_sync(_generate)
    except Exception as e:
        logger.exception("Banner generation failed after retries")
        return BannerOutput(error=type(e).__name__, error_code="RETRY_FAILED")


def is_banner_generation_available() -> bool:
    """Check if banner generation is available (GOOGLE_API_KEY is set).

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    """
    return google_api_key_status()
