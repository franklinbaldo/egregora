"""Banner/cover image generation using Gemini image generation API.

This module provides a legacy compatibility layer for the banner generation agent.
The core agent (in agent.py) returns Document objects with binary content.
This wrapper handles filesystem persistence for backward compatibility with
existing code that expects file paths.

Requires GOOGLE_API_KEY environment variable.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from pathlib import Path

from pydantic import BaseModel, Field

from egregora.agents.banner.agent import generate_banner_with_agent

logger = logging.getLogger(__name__)

_DEFAULT_IMAGE_EXTENSION = ".png"


def _save_image_to_disk(data_buffer: bytes, mime_type: str, output_dir: Path) -> Path:
    """Save image data to disk with content-based deterministic naming.

    This is a legacy compatibility function for the wrapper layer.
    The core agent (agent.py) does NOT touch the filesystem.

    Args:
        data_buffer: Image binary data
        mime_type: MIME type (e.g., 'image/png')
        output_dir: Directory to save the image

    Returns:
        Path to the saved file

    """
    file_extension = mimetypes.guess_extension(mime_type) or _DEFAULT_IMAGE_EXTENSION
    # Use content hash for deterministic, collision-resistant naming
    content_hash = hashlib.sha256(data_buffer).hexdigest()
    banner_filename = f"banner-{content_hash[:32]}{file_extension}"
    banner_path = output_dir / banner_filename

    output_dir.mkdir(parents=True, exist_ok=True)
    with banner_path.open("wb") as f:
        f.write(data_buffer)
    logger.info("Banner saved: %s (%d bytes)", banner_path.name, len(data_buffer))
    return banner_path


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

    This class delegates to the Pydantic-AI agent and handles filesystem persistence.
    The agent returns Document objects; this wrapper saves them to disk and returns paths.
    """

    def __init__(self, api_key: str | None = None, *, enabled: bool = True) -> None:
        """Initialize the banner generator.

        Args:
            api_key: Deprecated. API key is now read from GOOGLE_API_KEY environment variable.
            enabled: Whether banner generation is enabled.

        """
        self.enabled = enabled
        if not enabled:
            return
        # Validate API key is available (agent will fail if not)
        if not os.environ.get("GOOGLE_API_KEY"):
            msg = "Banner generation requires GOOGLE_API_KEY environment variable."
            raise ValueError(msg)

    def generate_banner(self, request: BannerRequest) -> BannerResult:
        """Generate a banner using the agent and save to disk.

        Args:
            request: Banner generation parameters (includes output_dir for saving)

        Returns:
            BannerResult with file path

        """
        if not self.enabled:
            return BannerResult(success=False, error="Banner generation disabled")

        # Call the agent (returns Document with binary content)
        agent_result = generate_banner_with_agent(
            post_title=request.post_title,
            post_summary=request.post_summary,
        )

        # Save to disk (legacy compatibility layer responsibility)
        if agent_result.success and agent_result.document:
            content = agent_result.document.content
            mime_type = agent_result.document.metadata.get("mime_type", "image/png")
            banner_path = _save_image_to_disk(content, mime_type, request.output_dir)

            return BannerResult(
                success=True,
                banner_path=banner_path,
                error=None,
            )

        return BannerResult(
            success=False,
            banner_path=None,
            error=agent_result.error,
        )


def generate_banner_for_post(
    post_title: str, post_summary: str, output_dir: Path, slug: str, api_key: str | None = None
) -> Path | None:
    """Convenience function to generate a banner for a post and save to disk.

    Args:
        post_title: The blog post title
        post_summary: Brief summary of the post
        output_dir: Directory to save the banner
        slug: Post slug (unused, kept for backward compatibility)
        api_key: Deprecated. API key is read from GOOGLE_API_KEY environment variable.

    Returns:
        Path to generated banner, or None if generation failed

    """
    try:
        if not os.environ.get("GOOGLE_API_KEY"):
            logger.warning("GOOGLE_API_KEY not set, banner generation skipped")
            return None

        # Call the agent (returns Document with binary content)
        agent_result = generate_banner_with_agent(
            post_title=post_title,
            post_summary=post_summary,
        )

        # Save to disk
        if agent_result.success and agent_result.document:
            content = agent_result.document.content
            mime_type = agent_result.document.metadata.get("mime_type", "image/png")
            return _save_image_to_disk(content, mime_type, output_dir)
        if agent_result.error:
            logger.error("Banner generation failed: %s", agent_result.error)
        return None
    except Exception:
        logger.exception("Banner generation failed")
        return None


def is_banner_generation_available() -> bool:
    """Check if banner generation is available (GOOGLE_API_KEY is set).

    Returns:
        True if GOOGLE_API_KEY environment variable is set

    """
    return os.environ.get("GOOGLE_API_KEY") is not None
