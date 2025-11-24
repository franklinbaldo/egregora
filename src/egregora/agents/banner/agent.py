"""Pydantic-AI powered banner generation agent.

This module implements the banner generation workflow using Pydantic-AI.
It decouples the creative direction (LLM) from the image generation (Tool).
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from egregora.data_primitives.document import Document, DocumentType
from egregora.utils.retry import RetryPolicy, retry_sync

logger = logging.getLogger(__name__)

# Constants
_DEFAULT_IMAGE_MODEL = "models/gemini-2.5-flash-image"
_BANNER_ASPECT_RATIO = "16:9"
_RESPONSE_MODALITIES_IMAGE = "IMAGE"
_RESPONSE_MODALITIES_TEXT = "TEXT"
_DEFAULT_IMAGE_EXTENSION = ".png"

# System prompt for the creative director agent
_CREATIVE_DIRECTOR_PROMPT = """You are a senior editorial illustrator and creative director for a modern blog.
Your goal is to design a striking, concept-driven cover/banner image for a blog post.

You will be given the title and summary of a post.
Your task is to:
1. Analyze the essence of the article.
2. Conceive a minimalist, abstract visual metaphor that captures this essence without literal depictions.
3. Formulate a precise image generation prompt that describes this visual concept.
4. Call the `generate_image_tool` with this refined prompt.

Design Principles:
- Style: Abstract, conceptual, minimalist modern editorial.
- Composition: Keep the UPPER 30% relatively clean for potential text overlay.
- Focus: Main visual interest in the LOWER 2/3.
- Colors: Bold but harmonious (2-4 colors max).
- NO text or typography in the image itself.
- NO photorealism or complex details.
- Use geometric forms, gradients, and symbolic elements.

Think like an artist, not a photographer.
"""


class BannerRequest(BaseModel):
    """Request parameters for banner generation."""

    post_title: str
    post_summary: str
    output_dir: Path
    slug: str


class BannerResult(BaseModel):
    """Result from banner generation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    banner_path: Path | None = None
    error: str | None = None
    document: Document | None = None


@dataclass
class BannerDeps:
    """Dependencies for the banner agent.

    This object is mutable to allow the tool to side-channel the result
    back to the caller, bypassing the LLM's inability to output binary data.
    """

    client: genai.Client
    output_dir: Path
    image_model: str = _DEFAULT_IMAGE_MODEL
    result: BannerResult | None = field(default=None)


def _save_image_asset(data_buffer: bytes, mime_type: str, output_dir: Path) -> Path:
    """Save image data to disk with content-based deterministic naming."""
    file_extension = mimetypes.guess_extension(mime_type) or _DEFAULT_IMAGE_EXTENSION
    content_hash = hashlib.sha256(data_buffer).digest()
    banner_uuid = uuid.UUID(bytes=content_hash[:16], version=5)
    banner_filename = f"{banner_uuid}{file_extension}"
    banner_path = output_dir / banner_filename

    with banner_path.open("wb") as f:
        f.write(data_buffer)
    logger.info("Banner saved to: %s", banner_path)
    return banner_path


def generate_image_tool(ctx: RunContext[BannerDeps], visual_prompt: str) -> str:
    """Generate an image using the configured image generation model.

    Args:
        ctx: Agent context containing dependencies
        visual_prompt: The detailed prompt for the image generation model

    Returns:
        Status message string. The actual result is stored in `ctx.deps.result`.

    """
    logger.info("Generating image with prompt: %s", visual_prompt[:100] + "...")

    # Ensure output directory exists
    ctx.deps.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=visual_prompt)])]
        generate_content_config = types.GenerateContentConfig(
            response_modalities=[_RESPONSE_MODALITIES_IMAGE, _RESPONSE_MODALITIES_TEXT],
            image_config=types.ImageConfig(aspect_ratio=_BANNER_ASPECT_RATIO),
        )

        # Use the client from deps to call the image model
        stream = ctx.deps.client.models.generate_content_stream(
            model=ctx.deps.image_model, contents=contents, config=generate_content_config
        )

        # Extract image from stream
        for chunk in stream:
            if not (chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts):
                continue
            part = chunk.candidates[0].content.parts[0]
            if part.inline_data and part.inline_data.data:
                inline_data = part.inline_data

                # Store result in deps side-channel
                ctx.deps.result = BannerResult(
                    success=True,
                    document=Document(
                        content=inline_data.data,
                        type=DocumentType.MEDIA,
                        metadata={"mime_type": inline_data.mime_type},
                    ),
                )
                return "Image generated successfully."

            # Log text feedback if any (sometimes model explains why it failed)
            if hasattr(chunk, "text") and chunk.text:
                logger.debug("Image gen response text: %s", chunk.text)

        ctx.deps.result = BannerResult(success=False, error="No image data received from API")
        return "Failed to generate image: No data received."

    except Exception as e:
        logger.exception("Image generation failed")
        ctx.deps.result = BannerResult(success=False, error=str(e))
        return f"Failed to generate image: {e}"


def generate_banner_with_agent(
    post_title: str, post_summary: str, output_dir: Path, api_key: str | None = None
) -> BannerResult:
    """Generate a banner using the Pydantic-AI agent workflow.

    Args:
        post_title: Title of the post
        post_summary: Summary of the post
        output_dir: Directory to save the banner
        api_key: Gemini API Key

    Returns:
        BannerResult

    """
    effective_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not effective_key:
        return BannerResult(success=False, error="No API Key provided")

    # Create dependencies with mutable result field
    client = genai.Client(api_key=effective_key)
    deps = BannerDeps(client=client, output_dir=output_dir)

    prompt = f"Title: {post_title}\n\nSummary: {post_summary}"

    # Instantiate Agent locally to inject API key into the Model
    # This solves the issue where the global agent relied on env vars
    provider = GoogleProvider(api_key=effective_key)
    model = GoogleModel("gemini-1.5-flash", provider=provider)
    agent = Agent(
        model,
        deps_type=BannerDeps,
        output_type=str,  # Agent returns a status string (from tool)
        system_prompt=_CREATIVE_DIRECTOR_PROMPT,
        tools=[generate_image_tool],
    )

    # Retry policy for the agent execution
    retry_policy = RetryPolicy()

    try:
        result = retry_sync(lambda: agent.run_sync(prompt, deps=deps), retry_policy)

        # Return the result from side-channel if available
        if deps.result:
            return deps.result

        # If no result was set but agent succeeded (unlikely with tool usage), return failure
        return BannerResult(
            success=False, error=f"Agent completed but produced no image result. Output: {result.data}"
        )

    except Exception as e:
        logger.exception("Banner agent run failed")
        return BannerResult(success=False, error=str(e))
