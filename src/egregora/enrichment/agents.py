"""Pydantic AI agents for enrichment tasks.

Factory functions create agents with configurable models from CLI/config.
Uses pydantic-ai string notation for model specification.
"""

from __future__ import annotations
import logging
import mimetypes
from typing import TYPE_CHECKING
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent
from egregora.prompt_templates import (
    AvatarEnrichmentPromptTemplate,
    DetailedMediaEnrichmentPromptTemplate,
    DetailedUrlEnrichmentPromptTemplate,
)

if TYPE_CHECKING:
    from pathlib import Path
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


def create_url_enrichment_agent(model: str) -> Agent[UrlEnrichmentContext, EnrichmentOutput]:
    """Create URL enrichment agent with specified model.

    Args:
        model: Model string in pydantic-ai format (e.g., 'google-gla:gemini-flash-latest')

    Returns:
        Configured agent for URL enrichment

    """
    agent = Agent[UrlEnrichmentContext, EnrichmentOutput](model, output_type=EnrichmentOutput)

    @agent.system_prompt
    def url_system_prompt(ctx: RunContext[UrlEnrichmentContext]) -> str:
        """Generate system prompt for URL enrichment."""
        template = DetailedUrlEnrichmentPromptTemplate(
            url=ctx.deps.url,
            original_message=ctx.deps.original_message,
            sender_uuid=ctx.deps.sender_uuid,
            date=ctx.deps.date,
            time=ctx.deps.time,
        )
        return template.render()

    return agent


def create_media_enrichment_agent(model: str) -> Agent[MediaEnrichmentContext, EnrichmentOutput]:
    """Create media enrichment agent with specified model.

    Args:
        model: Model string in pydantic-ai format (e.g., 'google-gla:gemini-flash-latest')

    Returns:
        Configured agent for media enrichment

    """
    agent = Agent[MediaEnrichmentContext, EnrichmentOutput](model, output_type=EnrichmentOutput)

    @agent.system_prompt
    def media_system_prompt(ctx: RunContext[MediaEnrichmentContext]) -> str:
        """Generate system prompt for media enrichment."""
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


def create_avatar_enrichment_agent(model: str) -> Agent[AvatarEnrichmentContext, AvatarModerationOutput]:
    """Create avatar enrichment agent with specified model.

    Args:
        model: Model string in pydantic-ai format (e.g., 'google-gla:gemini-flash-latest')

    Returns:
        Configured agent for avatar moderation

    """
    agent = Agent[AvatarEnrichmentContext, AvatarModerationOutput](model, output_type=AvatarModerationOutput)

    @agent.system_prompt
    def avatar_system_prompt(ctx: RunContext[AvatarEnrichmentContext]) -> str:
        """Generate system prompt for avatar moderation."""
        template = AvatarEnrichmentPromptTemplate(
            media_filename=ctx.deps.media_filename, media_path=ctx.deps.media_path
        )
        return template.render()

    return agent


def load_file_as_binary_content(file_path: Path, max_size_mb: int = 20) -> BinaryContent:
    """Load a file as BinaryContent for pydantic-ai agents.

    Args:
        file_path: Path to the file
        max_size_mb: Maximum file size in megabytes (default: 20MB)

    Returns:
        BinaryContent object with file bytes and media type

    Raises:
        ValueError: If file size exceeds max_size_mb
        FileNotFoundError: If file doesn't exist

    """
    if not file_path.exists():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)
    file_size = file_path.stat().st_size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        size_mb = file_size / (1024 * 1024)
        msg = f"File too large: {size_mb:.2f}MB exceeds {max_size_mb}MB limit. File: {file_path.name}"
        raise ValueError(msg)
    media_type, _ = mimetypes.guess_type(str(file_path))
    if not media_type:
        media_type = "application/octet-stream"
    file_bytes = file_path.read_bytes()
    return BinaryContent(data=file_bytes, media_type=media_type)
