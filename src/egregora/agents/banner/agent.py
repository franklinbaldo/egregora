"""Pydantic-AI powered banner generation agent.

This module implements banner generation using a single multimodal model
(gemini-2.0-flash-exp-image) that directly generates images from text prompts.

No separate "creative director" LLM - the image model handles both creative
interpretation and generation in a single API call.
"""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import errors as google_exceptions
from pydantic import BaseModel, Field
from tenacity import Retrying

from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider
from egregora.agents.banner.image_generation import ImageGenerationRequest
from egregora.config import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
from egregora.llm.retry import RETRY_IF, RETRY_STOP, RETRY_WAIT
from egregora.resources.prompts import render_prompt

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

    # Document is a dataclass (not a Pydantic model), so no ConfigDict/arbitrary-types hook is required.
    document: Document | None = None
    error: str | None = None
    error_code: str | None = Field(
        default=None,
        description="Optional machine-readable code describing banner failures.",
    )
    debug_text: str | None = Field(
        default=None,
        description="Raw debug output from the image provider, when available.",
    )

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

    except google_exceptions.APIError as e:
        logger.exception("Banner image generation failed for post '%s'", input_data.post_title)
        return BannerOutput(error=type(e).__name__, error_code="GENERATION_EXCEPTION")


def generate_banner(
    post_title: str,
    post_summary: str,
    slug: str | None = None,
    language: str = "pt-BR",
) -> BannerOutput:
    """Generate a banner image using the Gemini multimodal image model.

    This is a single-model approach: gemini-2.0-flash-exp-image handles both
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
    if not is_banner_generation_available():
        return BannerOutput(
            error="Banner generation is not available. Please set GOOGLE_API_KEY.",
            error_code="NOT_CONFIGURED",
        )
    # Client reads GOOGLE_API_KEY from environment automatically
    config = EgregoraConfig()
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    # Load configuration
    image_model = config.models.banner

    input_data = BannerInput(
        post_title=post_title,
        post_summary=post_summary,
        slug=slug,
        language=language,
    )
    prompt = _build_image_prompt(input_data)

    try:
        generation_request = ImageGenerationRequest(
            prompt=prompt,
            response_modalities=config.image_generation.response_modalities,
            aspect_ratio=config.image_generation.aspect_ratio,
        )
        for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
            with attempt:
                return _generate_banner_image(client, input_data, image_model, generation_request)

        return BannerOutput(error="Banner generation failed (unreachable)", error_code="GENERATION_FAILED")
    except google_exceptions.APIError as e:
        logger.exception("Banner generation failed after retries")
        return BannerOutput(error=type(e).__name__, error_code="GENERATION_FAILED")


def is_banner_generation_available() -> bool:
    """Check if banner generation is available (GOOGLE_API_KEY is set).

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    """
    skip_validation = os.getenv("EGREGORA_SKIP_API_KEY_VALIDATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }
    if skip_validation:
        return True

    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
