"""Banner/cover image generation using Gemini image generation API.

This module uses Pydantic-AI to orchestrate the creative direction and generation
of blog post banners. It employs a two-step process:
1. An LLM Agent acts as a Creative Director to design the visual concept.
2. A Tool calls the Gemini Image Generation API to render the image.

Requires GOOGLE_API_KEY environment variable.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import BaseModel, Field

from egregora.agents.banner.agent import _save_image_asset, generate_banner_with_agent

logger = logging.getLogger(__name__)


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
    """Legacy wrapper for banner generation to maintain compatibility.

    This class now delegates to the Pydantic-AI agent implementation.
    """

    def __init__(self, api_key: str | None = None, *, enabled: bool = True) -> None:
        """Initialize the banner generator.

        Args:
            api_key: Gemini API key. If None, reads from GOOGLE_API_KEY env var.
            enabled: Whether banner generation is enabled.

        """
        self.enabled = enabled
        if not enabled:
            return
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            msg = "Banner generation requires GOOGLE_API_KEY."
            raise ValueError(msg)

    def generate_banner(self, request: BannerRequest) -> BannerResult:
        """Generate a banner using the agent.

        Args:
            request: Banner generation parameters

        Returns:
            BannerResult

        """
        if not self.enabled:
            return BannerResult(success=False, error="Banner generation disabled")

        # Delegate to the new agent-based implementation
        result = generate_banner_with_agent(
            post_title=request.post_title,
            post_summary=request.post_summary,
            output_dir=request.output_dir,
            api_key=self.api_key,
        )

        # Legacy compatibility: If content is returned but no path, save it here
        banner_path = result.banner_path
        if result.success and result.document and not banner_path:
            # Persist to maintain legacy behavior
            request.output_dir.mkdir(parents=True, exist_ok=True)
            content = result.document.content
            mime_type = result.document.metadata.get("mime_type", "image/png")
            banner_path = _save_image_asset(content, mime_type, request.output_dir)

        return BannerResult(
            success=result.success,
            banner_path=banner_path,
            error=result.error,
        )


def generate_banner_for_post(
    post_title: str, post_summary: str, output_dir: Path, slug: str, api_key: str | None = None
) -> Path | None:
    """Convenience function to generate a banner for a post.

    Args:
        post_title: The blog post title
        post_summary: Brief summary of the post
        output_dir: Directory to save the banner
        slug: Post slug (unused in v2 logic, kept for compat)
        api_key: Optional Gemini API key

    Returns:
        Path to generated banner, or None if generation failed

    """
    try:
        effective_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not effective_key:
            return None

        result = generate_banner_with_agent(
            post_title=post_title,
            post_summary=post_summary,
            output_dir=output_dir,
            api_key=effective_key,
        )

        # Legacy fallback: Save if not already saved
        if result.success and result.document and not result.banner_path:
            output_dir.mkdir(parents=True, exist_ok=True)
            content = result.document.content
            mime_type = result.document.metadata.get("mime_type", "image/png")
            return _save_image_asset(content, mime_type, output_dir)

        return result.banner_path if result.success else None
    except Exception:
        logger.exception("Banner generation failed")
        return None


def is_banner_generation_available() -> bool:
    """Check if banner generation is available (GOOGLE_API_KEY is set).

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    """
    return os.environ.get("GOOGLE_API_KEY") is not None
