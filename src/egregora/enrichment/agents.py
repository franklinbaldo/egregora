"""Pydantic AI agents for enrichment tasks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from google import genai
from pydantic import BaseModel
from pydantic_ai import Agent

try:
    from pydantic_ai.models.google import GoogleModel, GoogleProvider
except ImportError:  # pragma: no cover - legacy SDKs
    from pydantic_ai.models.gemini import GeminiModel as GoogleModel  # type: ignore
    from pydantic_ai.models.gemini import GeminiModelSettings as GoogleProvider  # type: ignore

from egregora.prompt_templates import (
    AvatarEnrichmentPromptTemplate,
    DetailedMediaEnrichmentPromptTemplate,
    DetailedUrlEnrichmentPromptTemplate,
)
from egregora.utils.genai import call_with_retries_sync

logger = logging.getLogger(__name__)


class EnrichmentOutput(BaseModel):
    """Structured output for enrichment agents."""

    markdown: str


class AvatarModerationOutput(BaseModel):
    """Structured output for avatar moderation."""

    is_appropriate: bool
    reason: str
    description: str


@dataclass
class UrlEnrichmentContext:
    """Context for URL enrichment agent."""

    url: str
    original_message: str
    sender_uuid: str
    date: str
    time: str


@dataclass
class MediaEnrichmentContext:
    """Context for media enrichment agent."""

    media_type: str
    media_filename: str
    media_path: str
    original_message: str
    sender_uuid: str
    date: str
    time: str
    file_uri: str  # Uploaded file URI
    mime_type: str


@dataclass
class AvatarEnrichmentContext:
    """Context for avatar enrichment agent."""

    media_filename: str
    media_path: str
    file_uri: str  # Uploaded file URI


def create_url_enrichment_agent(
    model: str, client: genai.Client
) -> Agent[UrlEnrichmentContext, EnrichmentOutput]:
    """Create an agent for URL enrichment.

    Args:
        model: Model name to use (e.g., "models/gemini-2.0-flash-exp")
        client: Google GenAI client to use for API calls

    Returns:
        Configured pydantic-ai Agent
    """
    # Create provider with custom client
    provider = GoogleProvider(client=client)
    model_instance = GoogleModel(model, provider=provider)

    agent = Agent[UrlEnrichmentContext, EnrichmentOutput](
        model_instance,
        result_type=EnrichmentOutput,
        system_prompt=(
            "You are a helpful assistant that enriches URLs by providing detailed markdown descriptions. "
            "Generate clear, informative markdown content based on the URL and context provided."
        ),
    )

    @agent.system_prompt
    def url_system_prompt(ctx) -> str:
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
    model: str, client: genai.Client
) -> Agent[MediaEnrichmentContext, EnrichmentOutput]:
    """Create an agent for media enrichment.

    Args:
        model: Model name to use (e.g., "models/gemini-2.0-flash-thinking-exp")
        client: Google GenAI client to use for API calls

    Returns:
        Configured pydantic-ai Agent
    """
    # Create provider with custom client
    provider = GoogleProvider(client=client)
    model_instance = GoogleModel(model, provider=provider)

    agent = Agent[MediaEnrichmentContext, EnrichmentOutput](
        model_instance,
        result_type=EnrichmentOutput,
        system_prompt=(
            "You are a helpful assistant that enriches media files by providing detailed markdown descriptions. "
            "Analyze the media content and generate clear, informative markdown."
        ),
    )

    @agent.system_prompt
    def media_system_prompt(ctx) -> str:
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
    model: str, client: genai.Client
) -> Agent[AvatarEnrichmentContext, AvatarModerationOutput]:
    """Create an agent for avatar enrichment and moderation.

    Args:
        model: Model name to use (e.g., "models/gemini-2.0-flash-thinking-exp")
        client: Google GenAI client to use for API calls

    Returns:
        Configured pydantic-ai Agent
    """
    # Create provider with custom client
    provider = GoogleProvider(client=client)
    model_instance = GoogleModel(model, provider=provider)

    agent = Agent[AvatarEnrichmentContext, AvatarModerationOutput](
        model_instance,
        result_type=AvatarModerationOutput,
        system_prompt=(
            "You are a content moderation assistant. Analyze avatar images and determine if they are appropriate. "
            "Provide a clear reason and description."
        ),
    )

    @agent.system_prompt
    def avatar_system_prompt(ctx) -> str:
        """Generate system prompt from template."""
        template = AvatarEnrichmentPromptTemplate(
            media_filename=ctx.deps.media_filename,
            media_path=ctx.deps.media_path,
        )
        return template.render()

    return agent


def upload_file_for_enrichment(client: genai.Client, file_path: Path) -> tuple[str, str]:
    """Upload a file for enrichment and return URI and MIME type.

    Args:
        client: Gemini API client
        file_path: Path to file to upload

    Returns:
        Tuple of (file_uri, mime_type)

    Raises:
        RuntimeError: If upload fails
    """
    import time

    logger.debug("Uploading media file for enrichment: %s", file_path)

    try:
        uploaded_file = call_with_retries_sync(client.files.upload, file=str(file_path))

        # Wait for file to become ACTIVE (required before use)
        max_wait = 60  # seconds
        poll_interval = 2  # seconds
        elapsed = 0

        while uploaded_file.state.name != "ACTIVE":
            if elapsed >= max_wait:
                logger.warning(
                    "File %s did not become ACTIVE after %ds (state: %s)",
                    file_path,
                    max_wait,
                    uploaded_file.state.name,
                )
                break

            time.sleep(poll_interval)
            elapsed += poll_interval
            uploaded_file = call_with_retries_sync(client.files.get, name=uploaded_file.name)
            logger.debug(
                "Waiting for file %s to become ACTIVE (current: %s, elapsed: %ds)",
                file_path,
                uploaded_file.state.name,
                elapsed,
            )

        return uploaded_file.uri, uploaded_file.mime_type

    except Exception as e:
        logger.error("Failed to upload file %s: %s", file_path, e, exc_info=True)
        raise RuntimeError(f"File upload failed: {e}") from e
