"""Pydantic AI agents for enrichment tasks.

Factory functions create agents with configurable models from CLI/config.
Uses pydantic-ai string notation for model specification.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import AnyUrl, BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.google import GoogleModelSettings

from egregora.prompt_templates import render_prompt

if TYPE_CHECKING:
    from pydantic_ai.result import RunResult
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
    prompts_dir: Path | None = None  # Custom prompts directory


class MediaEnrichmentContext(BaseModel):
    """Context for media enrichment agent."""

    media_type: str
    media_filename: str
    media_path: str
    original_message: str
    sender_uuid: str
    date: str
    time: str
    prompts_dir: Path | None = None  # Custom prompts directory


class AvatarEnrichmentContext(BaseModel):
    """Context for avatar enrichment agent."""

    media_filename: str
    media_path: str
    prompts_dir: Path | None = None  # Custom prompts directory


def create_url_enrichment_agent(model: str) -> Agent[UrlEnrichmentContext, EnrichmentOutput]:
    """Create URL enrichment agent with specified model.

    Args:
        model: Pydantic-AI model id (e.g., 'google-gla:gemini-flash-latest')

    Returns:
        Configured agent for URL enrichment

    """
    agent = Agent[UrlEnrichmentContext, EnrichmentOutput](model, output_type=EnrichmentOutput)

    @agent.system_prompt
    def url_system_prompt(ctx: RunContext[UrlEnrichmentContext]) -> str:
        """Generate system prompt for URL enrichment."""
        return render_prompt(
            "enrichment/url_detailed.jinja",
            prompts_dir=ctx.deps.prompts_dir,
            url=ctx.deps.url,
            original_message=ctx.deps.original_message,
            sender_uuid=ctx.deps.sender_uuid,
            date=ctx.deps.date,
            time=ctx.deps.time,
        )

    return agent


def create_media_enrichment_agent(model: str) -> Agent[MediaEnrichmentContext, EnrichmentOutput]:
    """Create media enrichment agent with specified model.

    Args:
        model: Pydantic-AI model id (e.g., 'google-gla:gemini-flash-latest')

    Returns:
        Configured agent for media enrichment

    """
    agent = Agent[MediaEnrichmentContext, EnrichmentOutput](model, output_type=EnrichmentOutput)

    @agent.system_prompt
    def media_system_prompt(ctx: RunContext[MediaEnrichmentContext]) -> str:
        """Generate system prompt for media enrichment."""
        return render_prompt(
            "enrichment/media_detailed.jinja",
            prompts_dir=ctx.deps.prompts_dir,
            media_type=ctx.deps.media_type,
            media_filename=ctx.deps.media_filename,
            media_path=ctx.deps.media_path,
            original_message=ctx.deps.original_message,
            sender_uuid=ctx.deps.sender_uuid,
            date=ctx.deps.date,
            time=ctx.deps.time,
        )

    return agent


def create_avatar_enrichment_agent(model: str) -> Agent[AvatarEnrichmentContext, AvatarModerationOutput]:
    """Create avatar enrichment agent with specified model.

    Args:
        model: Pydantic-AI model id (e.g., 'google-gla:gemini-flash-latest')

    Returns:
        Configured agent for avatar moderation

    """
    agent = Agent[AvatarEnrichmentContext, AvatarModerationOutput](model, output_type=AvatarModerationOutput)

    @agent.system_prompt
    def avatar_system_prompt(ctx: RunContext[AvatarEnrichmentContext]) -> str:
        """Generate system prompt for avatar moderation."""
        return render_prompt(
            "enricher_avatar.jinja",
            prompts_dir=ctx.deps.prompts_dir,
            media_filename=ctx.deps.media_filename,
            media_path=ctx.deps.media_path,
        )

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


# ---------------------------------------------------------------------------
# Thin agent helpers (one agent per enrichment call)
#
# CONSOLIDATED (2025-11-19): Removed duplicate EnrichmentOut class.
# Now uses EnrichmentOutput everywhere for consistency.
# The alias below maintains backward compatibility.

# Alias for backward compatibility - use EnrichmentOutput for new code
EnrichmentOut = EnrichmentOutput


class UrlEnrichmentDeps(BaseModel):
    """Dependencies for URL enrichment agent (simple mode).

    For detailed enrichment with message context (sender, date, original message),
    use UrlEnrichmentContext with create_url_enrichment_agent() instead.

    The agent receives the pre-rendered system prompt from the factory, not prompts_dir.
    This keeps the prompt resolution logic in the factory where it belongs.
    """

    url: str
    # REMOVED (2025-11-19): prompts_dir moved to factory function
    # Agents should not know about prompt resolution - they receive rendered content


class MediaEnrichmentDeps(BaseModel):
    """Dependencies for media enrichment agent (simple mode).

    For detailed enrichment with message context (sender, date, original message),
    use MediaEnrichmentContext with create_media_enrichment_agent() instead.

    The agent receives the pre-rendered system prompt from the factory, not prompts_dir.
    This keeps the prompt resolution logic in the factory where it belongs.
    """

    # REMOVED (2025-11-19): prompts_dir moved to factory function
    # Agents should not know about prompt resolution - they receive rendered content


def make_url_agent(
    model_name: str, prompts_dir: Path | None = None
) -> Agent[UrlEnrichmentDeps, EnrichmentOut]:
    """Create a URL enrichment agent using Jinja templates with grounding enabled.

    The prompts_dir is captured in a closure, not passed through deps.
    This keeps prompt resolution logic in the factory where it belongs.
    """
    model_settings = GoogleModelSettings(google_tools=[{"url_context": {}}])

    agent = Agent[UrlEnrichmentDeps, EnrichmentOut](
        model=model_name,
        output_type=EnrichmentOut,
        model_settings=model_settings,
    )

    # Capture prompts_dir in closure - deps should only contain runtime data
    captured_prompts_dir = prompts_dir

    @agent.system_prompt
    def url_system_prompt(ctx: RunContext[UrlEnrichmentDeps]) -> str:
        return render_prompt(
            "enrichment/url_simple.jinja",
            prompts_dir=captured_prompts_dir,
            url=ctx.deps.url,
        )

    return agent


def make_media_agent(
    model_name: str, prompts_dir: Path | None = None
) -> Agent[MediaEnrichmentDeps, EnrichmentOut]:
    """Create a minimal media enrichment agent using Jinja templates.

    The prompts_dir is captured in a closure and the system prompt is pre-rendered.
    This keeps prompt resolution logic in the factory where it belongs.
    """
    # Pre-render the system prompt since it doesn't depend on runtime data
    rendered_prompt = render_prompt(
        "enrichment/media_simple.jinja",
        prompts_dir=prompts_dir,
    )

    agent = Agent[MediaEnrichmentDeps, EnrichmentOut](
        model=model_name,
        output_type=EnrichmentOut,
        system_prompt=rendered_prompt,  # Pass pre-rendered prompt directly
    )

    return agent


def _sanitize_prompt_input(text: str, max_length: int = 2000) -> str:
    """Sanitize user input for LLM prompts to prevent prompt injection."""
    text = text[:max_length]
    cleaned = "".join(char for char in text if char.isprintable() or char in "\n\t")
    return "\n".join(line for line in cleaned.split("\n") if line.strip())


def run_url_enrichment(agent: Agent[UrlEnrichmentDeps, EnrichmentOut], url: str | AnyUrl) -> str:
    """Run URL enrichment with grounding to fetch actual content.

    The prompts_dir is already captured in the agent factory closure.
    Deps only contain runtime data (the URL to enrich).
    """
    url_str = str(url)
    sanitized_url = _sanitize_prompt_input(url_str, max_length=2000)

    deps = UrlEnrichmentDeps(url=url_str)
    prompt = (
        "Fetch and summarize the content at this URL. Include the main topic, key points, and any important metadata "
        "(author, date, etc.).\n\nURL: {sanitized_url}"
    )
    prompt = prompt.format(sanitized_url=sanitized_url)

    result: RunResult[EnrichmentOut] = agent.run_sync(prompt, deps=deps)
    output = getattr(result, "data", getattr(result, "output", result))
    return output.markdown.strip()


def run_media_enrichment(
    agent: Agent[MediaEnrichmentDeps, EnrichmentOut],
    file_path: Path,
    mime_hint: str | None = None,
) -> str:
    """Run media enrichment with a single agent call.

    The prompts_dir is already captured in the agent factory closure.
    Deps are empty since MediaEnrichmentDeps has no runtime data fields.
    """
    deps = MediaEnrichmentDeps()
    desc = "Describe this media file in 2-3 sentences, highlighting what a reader would learn by viewing it."
    sanitized_filename = _sanitize_prompt_input(file_path.name, max_length=255)
    sanitized_mime = _sanitize_prompt_input(mime_hint, max_length=50) if mime_hint else None
    hint_text = f" ({sanitized_mime})" if sanitized_mime else ""
    prompt = f"{desc}\nFILE: {sanitized_filename}{hint_text}"

    binary_content: BinaryContent = load_file_as_binary_content(file_path)
    message_content = [prompt, binary_content]

    result: RunResult[EnrichmentOut] = agent.run_sync(message_content, deps=deps)
    output = getattr(result, "data", getattr(result, "output", result))
    return output.markdown.strip()


__all__ = [
    "AvatarEnrichmentContext",
    "AvatarModerationOutput",
    "EnrichmentOut",
    "EnrichmentOutput",
    "MediaEnrichmentContext",
    "MediaEnrichmentDeps",
    "UrlEnrichmentContext",
    "UrlEnrichmentDeps",
    "create_avatar_enrichment_agent",
    "create_media_enrichment_agent",
    "create_url_enrichment_agent",
    "load_file_as_binary_content",
    "make_media_agent",
    "make_url_agent",
    "run_media_enrichment",
    "run_url_enrichment",
]
