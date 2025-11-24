"""Banner/cover image generation using Gemini image generation API.

This module uses Google's Gemini image generation API directly (not pydantic-ai)
because image generation requires streaming binary data handling that isn't yet
supported by pydantic-ai's text-focused agent interface.

Requires GOOGLE_API_KEY environment variable or explicit api_key parameter.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import uuid
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Constants for image generation
_DEFAULT_MODEL = "models/gemini-2.5-flash-image"
_BANNER_ASPECT_RATIO = "16:9"
_RESPONSE_MODALITIES_IMAGE = "IMAGE"
_RESPONSE_MODALITIES_TEXT = "TEXT"
_DEFAULT_IMAGE_EXTENSION = ".png"


class BannerRequest(BaseModel):
    """Request parameters for banner generation."""

    post_title: str = Field(description="The blog post title")
    post_summary: str = Field(description="Brief summary of the post")
    output_dir: Path = Field(description="Directory to save the generated banner")
    slug: str = Field(description="Post slug (used for filename)")


class BannerResult(BaseModel):
    """Result from banner generation."""

    success: bool = Field(description="Whether banner was generated successfully")
    banner_path: Path | None = Field(default=None, description="Path to generated banner")
    error: str | None = Field(default=None, description="Error message if generation failed")


class BannerGenerator:
    """Generate cover images for blog posts using Gemini 2.5 Flash Image.

    This is a Gemini-specific feature that requires GOOGLE_API_KEY.
    The generator can be disabled by not providing an API key, in which case
    all generation attempts will return None gracefully.
    """

    def __init__(self, api_key: str | None = None, *, enabled: bool = True) -> None:
        """Initialize the banner generator.

        Args:
            api_key: Gemini API key. If None, reads from GOOGLE_API_KEY env var.
            enabled: Whether banner generation is enabled. If False, skips all generation.

        Raises:
            ValueError: If enabled=True but no API key is available

        """
        self.enabled = enabled
        if not enabled:
            logger.info("Banner generation disabled")
            self.client = None
            self.model = None
            self.api_key = None
            return
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            msg = "Banner generation requires GOOGLE_API_KEY. Set environment variable or pass api_key parameter, or set enabled=False to disable banner generation."
            raise ValueError(msg)
        self.client = genai.Client(api_key=self.api_key)
        # Default model (can be overridden via config or passed in __init__)
        self.model = _DEFAULT_MODEL

    def _extract_image_from_stream(self, stream, output_dir: Path, post_title: str) -> BannerResult:
        """Extract and save image data from API response stream.

        Args:
            stream: Generator yielding response chunks from Gemini API
            output_dir: Directory to save the generated image
            post_title: Title of the post (for logging)

        Returns:
            BannerResult with success status and path (if successful)

        """
        for chunk in stream:
            if not (chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts):
                continue
            part = chunk.candidates[0].content.parts[0]
            if part.inline_data and part.inline_data.data:
                inline_data = part.inline_data
                banner_path = self._save_image_asset(inline_data.data, inline_data.mime_type, output_dir)
                return BannerResult(success=True, banner_path=banner_path)
            if hasattr(chunk, "text") and chunk.text:
                logger.debug("Gemini response: %s", chunk.text)
        logger.warning("No image generated for post: %s", post_title)
        return BannerResult(success=False, error="No image data received from API")

    def _save_image_asset(self, data_buffer: bytes, mime_type: str, output_dir: Path) -> Path:
        """Save image data to disk with content-based deterministic naming.

        Args:
            data_buffer: Raw image bytes
            mime_type: MIME type of the image
            output_dir: Directory to save the image

        Returns:
            Path to the saved image file

        """
        file_extension = mimetypes.guess_extension(mime_type) or _DEFAULT_IMAGE_EXTENSION
        # Use content-based UUID5 for deterministic naming (like other media)
        content_hash = hashlib.sha256(data_buffer).digest()
        banner_uuid = uuid.UUID(bytes=content_hash[:16], version=5)
        banner_filename = f"{banner_uuid}{file_extension}"
        banner_path = output_dir / banner_filename

        with banner_path.open("wb") as f:
            f.write(data_buffer)
        logger.info("Banner saved to: %s", banner_path)
        return banner_path

    def generate_banner(self, request: BannerRequest) -> BannerResult:
        """Generate a banner image for a blog post.

        Args:
            request: Banner generation parameters

        Returns:
            BannerResult with success status and path (if successful)

        """
        if not self.enabled:
            logger.info("Banner generation disabled, skipping: %s", request.post_title)
            return BannerResult(success=False, error="Banner generation disabled (no GOOGLE_API_KEY)")
        request.output_dir.mkdir(parents=True, exist_ok=True)
        prompt = self._build_prompt(request.post_title, request.post_summary)
        try:
            logger.info("Generating banner for post: %s", request.post_title)
            contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
            generate_content_config = types.GenerateContentConfig(
                response_modalities=[_RESPONSE_MODALITIES_IMAGE, _RESPONSE_MODALITIES_TEXT],
                image_config=types.ImageConfig(
                    aspect_ratio=_BANNER_ASPECT_RATIO
                ),  # Widescreen for blog banners
                system_instruction=[
                    types.Part.from_text(
                        text="You are a senior editorial illustrator for a modern blog. Your job is to translate an article into a striking, concept-driven cover/banner image that is legible at small sizes, brand-consistent, and accessible. Create minimalist, abstract representations that capture the essence of the article without literal depictions. Use bold colors, clear composition, and modern design principles."
                    )
                ],
            )
            stream = self.client.models.generate_content_stream(
                model=self.model, contents=contents, config=generate_content_config
            )
            return self._extract_image_from_stream(stream, request.output_dir, request.post_title)
        except Exception as e:
            logger.error("Failed to generate banner for %s: %s", request.post_title, e, exc_info=True)
            return BannerResult(success=False, error=str(e))

    def _build_prompt(self, title: str, summary: str) -> str:
        """Build the prompt for banner image generation.

        Args:
            title: Post title
            summary: Post summary

        Returns:
            Prompt string for image generation

        """
        return f"""Create a striking cover image for this blog post:

Title: {title}

Summary: {summary}

Design Requirements:
- Aspect ratio: 16:9 (widescreen banner/header)
- Composition: IMPORTANT - Keep the UPPER 30% relatively clean and simple to allow for text overlay
- Style: Abstract, conceptual, minimalist modern editorial
- Color palette: Bold but harmonious (2-4 colors maximum)
- Visual focus: Place the main visual interest in the LOWER 2/3 of the frame
- Avoid: Literal illustrations, complex text, photorealism, excessive detail

Technical Requirements:
- Do NOT include any text or typography in the image itself
- Create clear focal point in lower portion
- Use high contrast for good legibility
- Design should scale well from thumbnail to full-width display

The image should evoke the article's essence through abstract visual metaphor.
Use geometric forms, gradients, or symbolic elements rather than literal depictions.
Think editorial illustration, not stock photography."""


def generate_banner_for_post(
    post_title: str, post_summary: str, output_dir: Path, slug: str, api_key: str | None = None
) -> Path | None:
    """Convenience function to generate a banner for a post.

    This function gracefully handles missing API keys by returning None
    instead of raising an error.

    Args:
        post_title: The blog post title
        post_summary: Brief summary of the post
        output_dir: Directory to save the banner
        slug: Post slug (for filename)
        api_key: Optional Gemini API key (reads from GOOGLE_API_KEY env if not provided)

    Returns:
        Path to generated banner, or None if generation failed or is disabled

    """
    try:
        effective_key = api_key or os.environ.get("GOOGLE_API_KEY")
        enabled = effective_key is not None
        generator = BannerGenerator(api_key=api_key, enabled=enabled)
        request = BannerRequest(
            post_title=post_title, post_summary=post_summary, output_dir=output_dir, slug=slug
        )
        result = generator.generate_banner(request)
    except Exception as e:
        logger.error("Banner generation failed: %s", e, exc_info=True)
        return None
    else:
        return result.banner_path if result.success else None


def is_banner_generation_available() -> bool:
    """Check if banner generation is available (GOOGLE_API_KEY is set).

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    """
    return os.environ.get("GOOGLE_API_KEY") is not None
