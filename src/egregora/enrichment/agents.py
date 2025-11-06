"""Pydantic AI agents for enrichment tasks."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from google import genai
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from egregora.prompt_templates import (
    AvatarEnrichmentPromptTemplate,
    DetailedMediaEnrichmentPromptTemplate,
    DetailedUrlEnrichmentPromptTemplate,
)

logger = logging.getLogger(__name__)


class EnrichmentOutput(BaseModel):
    """Structured output for enrichment agents."""

    markdown: str


class AvatarModerationOutput(BaseModel):
    """Structured output for avatar moderation."""

    is_appropriate: bool
    reason: str
    description: str


class UrlEnrichmentContext(BaseModel):
    """Context for URL enrichment agent."""

    url: str
    original_message: str
    sender_uuid: str
    date: str
    time: str


class MediaEnrichmentContext(BaseModel):
    """Context for media enrichment agent."""

    media_type: str
    media_filename: str
    media_path: str
    original_message: str
    sender_uuid: str
    date: str
    time: str


class AvatarEnrichmentContext(BaseModel):
    """Context for avatar enrichment agent."""

    media_filename: str
    media_path: str


def create_url_enrichment_agent(
    model_name: str,
    client: genai.Client | None = None,
) -> Agent[UrlEnrichmentContext, EnrichmentOutput]:
    """Create an agent for URL enrichment.

    Args:
        model_name: Model name to use (e.g., "gemini-2.0-flash-exp")
        client: Optional genai.Client. If provided, will be used for inference.
                If None, uses GOOGLE_API_KEY from environment.

    Returns:
        Configured pydantic-ai Agent
    """
    # Create model with optional client
    if client:
        provider = GoogleProvider(client=client)
        model = GoogleModel(model_name, provider=provider)
    else:
        model = GoogleModel(model_name)

    agent = Agent[UrlEnrichmentContext, EnrichmentOutput](
        model,
        output_type=EnrichmentOutput,
    )

    @agent.system_prompt
    def url_system_prompt(ctx: RunContext[UrlEnrichmentContext]) -> str:
        """Generate system prompt from template."""
        template = DetailedUrlEnrichmentPromptTemplate(
            url=ctx.deps.url,
            original_message=ctx.deps.original_message,
            sender_uuid=ctx.deps.sender_uuid,
            date=ctx.deps.date,
            time=ctx.deps.time,
        )
        return template.render()

    return agent


def create_media_enrichment_agent(
    model_name: str,
    client: genai.Client | None = None,
) -> Agent[MediaEnrichmentContext, EnrichmentOutput]:
    """Create an agent for media enrichment.

    Args:
        model_name: Model name to use (e.g., "gemini-2.0-flash-exp")
        client: Optional genai.Client. If provided, will be used for inference.
                If None, uses GOOGLE_API_KEY from environment.

    Returns:
        Configured pydantic-ai Agent
    """
    # Create model with optional client
    if client:
        provider = GoogleProvider(client=client)
        model = GoogleModel(model_name, provider=provider)
    else:
        model = GoogleModel(model_name)

    agent = Agent[MediaEnrichmentContext, EnrichmentOutput](
        model,
        output_type=EnrichmentOutput,
    )

    @agent.system_prompt
    def media_system_prompt(ctx: RunContext[MediaEnrichmentContext]) -> str:
        """Generate system prompt from template."""
        template = DetailedMediaEnrichmentPromptTemplate(
            media_type=ctx.deps.media_type,
            media_filename=ctx.deps.media_filename,
            media_path=ctx.deps.media_path,
            original_message=ctx.deps.original_message,
            sender_uuid=ctx.deps.sender_uuid,
            date=ctx.deps.date,
            time=ctx.deps.time,
        )
        return template.render()

    return agent


def create_avatar_enrichment_agent(
    model_name: str,
    client: genai.Client | None = None,
) -> Agent[AvatarEnrichmentContext, AvatarModerationOutput]:
    """Create an agent for avatar enrichment and moderation.

    Args:
        model_name: Model name to use (e.g., "gemini-2.0-flash-exp")
        client: Optional genai.Client. If provided, will be used for inference.
                If None, uses GOOGLE_API_KEY from environment.

    Returns:
        Configured pydantic-ai Agent
    """
    # Create model with optional client
    if client:
        provider = GoogleProvider(client=client)
        model = GoogleModel(model_name, provider=provider)
    else:
        model = GoogleModel(model_name)

    agent = Agent[AvatarEnrichmentContext, AvatarModerationOutput](
        model,
        output_type=AvatarModerationOutput,
    )

    @agent.system_prompt
    def avatar_system_prompt(ctx: RunContext[AvatarEnrichmentContext]) -> str:
        """Generate system prompt from template."""
        template = AvatarEnrichmentPromptTemplate(
            media_filename=ctx.deps.media_filename,
            media_path=ctx.deps.media_path,
        )
        return template.render()

    return agent


def load_file_as_binary_content(file_path: Path) -> BinaryContent:
    """Load a file and return as pydantic-ai BinaryContent.

    Args:
        file_path: Path to file to load

    Returns:
        BinaryContent with file data and MIME type

    Raises:
        RuntimeError: If file loading fails
    """
    logger.debug("Loading media file: %s", file_path)

    try:
        # Read file bytes
        file_data = file_path.read_bytes()

        # Infer MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            # Fallback based on extension
            ext = file_path.suffix.lower()
            mime_type_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".mp4": "video/mp4",
                ".mp3": "audio/mpeg",
                ".pdf": "application/pdf",
            }
            mime_type = mime_type_map.get(ext, "application/octet-stream")

        logger.debug(f"Loaded {len(file_data)} bytes with MIME type {mime_type}")

        return BinaryContent(data=file_data, media_type=mime_type)

    except Exception as e:
        logger.error(f"Failed to load file {file_path}: {e}", exc_info=True)
        raise RuntimeError(f"File loading failed: {e}") from e
