"""Pydantic-AI powered banner generation agent.

This module implements the banner generation workflow using Pydantic-AI.
It decouples the creative direction (LLM) from the image generation (Tool).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, RunContext

from egregora.data_primitives.document import Document, DocumentType
from egregora.utils.retry import RetryPolicy, retry_sync

logger = logging.getLogger(__name__)

# Constants
_DEFAULT_IMAGE_MODEL = "models/gemini-2.5-flash-image"
_BANNER_ASPECT_RATIO = "16:9"
_RESPONSE_MODALITIES_IMAGE = "IMAGE"
_RESPONSE_MODALITIES_TEXT = "TEXT"

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


class BannerResult(BaseModel):
    """Result from banner generation.

    The agent returns a Document with binary content (type=MEDIA) or an error.
    Filesystem operations (saving, paths, URLs) are handled by upper layers.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    document: Document | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        """True if a document was successfully generated."""
        return self.document is not None


@dataclass(frozen=True)
class BannerDeps:
    """Dependencies for the banner agent."""

    client: genai.Client
    image_model: str = _DEFAULT_IMAGE_MODEL


# Define the agent
# Using the pattern: Agent(model, deps_type=..., output_type=..., system_prompt=...)
# Note: Using 'output_type' as required by Pydantic-AI 0.0.14+
banner_agent = Agent(
    "google-gla:gemini-1.5-flash",
    deps_type=BannerDeps,
    output_type=BannerResult,
    system_prompt=_CREATIVE_DIRECTOR_PROMPT,
)


@banner_agent.tool
def generate_image_tool(ctx: RunContext[BannerDeps], visual_prompt: str) -> BannerResult:
    """Generate an image using the configured image generation model.

    Args:
        ctx: Agent context containing dependencies
        visual_prompt: The detailed prompt for the image generation model

    Returns:
        BannerResult with document (bytes content) or error

    """
    logger.info("Generating banner image with prompt: %s...", visual_prompt[:100])

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

                # Return Document with binary content (no filesystem operations)
                return BannerResult(
                    document=Document(
                        content=inline_data.data,
                        type=DocumentType.MEDIA,
                        metadata={"mime_type": inline_data.mime_type},
                    ),
                )

            # Log text feedback if any (sometimes model explains why it failed)
            if hasattr(chunk, "text") and chunk.text:
                logger.debug("Image gen response text: %s", chunk.text)

        return BannerResult(error="No image data received from API")

    except Exception as e:
        logger.exception("Image generation failed")
        return BannerResult(error=str(e))


def generate_banner_with_agent(post_title: str, post_summary: str) -> BannerResult:
    """Generate a banner using the Pydantic-AI agent workflow.

    The agent returns a Document with binary image content. Filesystem operations
    (saving to disk, URL generation) are handled by upper layers (OutputAdapter).

    Args:
        post_title: Title of the post
        post_summary: Summary of the post

    Returns:
        BannerResult with document (binary content) or error

    """
    # Client reads GOOGLE_API_KEY from environment automatically
    client = genai.Client()
    deps = BannerDeps(client=client)

    prompt = f"Title: {post_title}\n\nSummary: {post_summary}"

    # Retry policy for the agent execution
    retry_policy = RetryPolicy()

    try:
        result = retry_sync(lambda: banner_agent.run_sync(prompt, deps=deps), retry_policy)
        data = result.data

        # Validate that the agent returned the expected type
        if not isinstance(data, BannerResult):
            logger.error("Unexpected agent output type: %r", type(data))
            return BannerResult(error="Agent did not return a BannerResult")
        return data
    except Exception as e:
        logger.exception("Banner agent run failed")
        return BannerResult(error=str(e))
