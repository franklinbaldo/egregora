"""Thin pydantic-ai agents for enrichment - one agent per kind, one call per item.

This module implements the "thin-agent pattern": minimal agents with simple prompts,
no batching or job orchestration. Each enrichment is a single agent.run_sync() call.

Usage:
    url_agent = make_url_agent("google-gla:gemini-flash-latest")
    markdown = run_url_enrichment(url_agent, "https://example.com")

    media_agent = make_media_agent("google-gla:gemini-flash-latest")
    markdown = run_media_enrichment(media_agent, Path("image.jpg"))
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import AnyUrl, BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models.google import GoogleModelSettings

from egregora.enrichment.agents import load_file_as_binary_content
from egregora.prompt_templates import MediaEnrichmentPromptTemplate, UrlEnrichmentPromptTemplate

if TYPE_CHECKING:
    from pydantic_ai.result import RunResult

logger = logging.getLogger(__name__)

# --- Typed output for pydantic-ai to parse ---


class EnrichmentOut(BaseModel):
    """Structured output for enrichment agents."""

    markdown: str


# --- Dependency types for prompt rendering ---


class UrlEnrichmentDeps(BaseModel):
    """Dependencies for URL enrichment agent."""

    url: str
    site_root: Path | None = None


class MediaEnrichmentDeps(BaseModel):
    """Dependencies for media enrichment agent."""

    site_root: Path | None = None


def make_url_agent(model_name: str, site_root: Path | None = None) -> Agent[UrlEnrichmentDeps, EnrichmentOut]:
    """Create a URL enrichment agent using Jinja templates with grounding enabled.

    Enables Gemini URL context grounding to fetch and read actual URL content
    instead of guessing from URL structure.

    Args:
        model_name: Pydantic-AI model string (e.g., "google-gla:gemini-flash-latest")
        site_root: Site root for custom prompt overrides

    Returns:
        Configured pydantic-ai Agent for URL enrichment with grounding

    """
    # Enable URL context grounding for Google models
    model_settings = GoogleModelSettings(
        google_tools=[{"url_context": {}}]  # Enable URL context grounding
    )

    agent = Agent[UrlEnrichmentDeps, EnrichmentOut](
        model=model_name,
        output_type=EnrichmentOut,
        model_settings=model_settings,
    )

    @agent.system_prompt
    def url_system_prompt(ctx: RunContext[UrlEnrichmentDeps]) -> str:
        """Generate system prompt from Jinja template."""
        template = UrlEnrichmentPromptTemplate(url=ctx.deps.url, site_root=ctx.deps.site_root)
        return template.render()

    return agent


def make_media_agent(
    model_name: str, site_root: Path | None = None
) -> Agent[MediaEnrichmentDeps, EnrichmentOut]:
    """Create a minimal media enrichment agent using Jinja templates.

    Args:
        model_name: Pydantic-AI model string (e.g., "google-gla:gemini-flash-latest")
        site_root: Site root for custom prompt overrides

    Returns:
        Configured pydantic-ai Agent for media enrichment

    """
    agent = Agent[MediaEnrichmentDeps, EnrichmentOut](
        model=model_name,
        output_type=EnrichmentOut,
    )

    @agent.system_prompt
    def media_system_prompt(ctx: RunContext[MediaEnrichmentDeps]) -> str:
        """Generate system prompt from Jinja template."""
        template = MediaEnrichmentPromptTemplate(site_root=ctx.deps.site_root)
        return template.render()

    return agent


# --- Single-call helpers ---


def run_url_enrichment(
    agent: Agent[UrlEnrichmentDeps, EnrichmentOut], url: str | AnyUrl, site_root: Path | None = None
) -> str:
    """Run URL enrichment with grounding to fetch actual content.

    Uses Gemini URL context grounding to fetch and read the actual page content
    instead of guessing from URL structure. This provides much higher quality
    enrichment with accurate summaries, metadata, and key points.

    Args:
        agent: Configured URL enrichment agent (with grounding enabled)
        url: URL to enrich
        site_root: Site root for custom prompt overrides

    Returns:
        Markdown content describing the actual URL content

    Raises:
        Exception: If agent call fails (let errors propagate)

    """
    url_str = str(url)
    deps = UrlEnrichmentDeps(url=url_str, site_root=site_root)
    prompt = f"Fetch and summarize the content at this URL. Include the main topic, key points, and any important metadata (author, date, etc.).\n\nURL: {url_str}"
    result: RunResult[EnrichmentOut] = agent.run_sync(prompt, deps=deps)
    # pydantic-ai 0.0.14+ uses .data attribute
    output = getattr(result, "data", getattr(result, "output", result))
    return output.markdown.strip()


def run_media_enrichment(
    agent: Agent[MediaEnrichmentDeps, EnrichmentOut],
    file_path: Path,
    mime_hint: str | None = None,
    site_root: Path | None = None,
) -> str:
    """Run media enrichment with a single agent call.

    Args:
        agent: Configured media enrichment agent
        file_path: Path to media file
        mime_hint: Optional MIME type hint (e.g., "image", "video")
        site_root: Site root for custom prompt overrides

    Returns:
        Markdown content describing the media

    Raises:
        Exception: If agent call fails (let errors propagate)

    """
    deps = MediaEnrichmentDeps(site_root=site_root)
    desc = "Describe this media file in 2-3 sentences, highlighting what a reader would learn by viewing it."
    hint_text = f" ({mime_hint})" if mime_hint else ""
    prompt = f"{desc}\nFILE: {file_path.name}{hint_text}"

    # Load file as BinaryContent for vision models
    binary_content: BinaryContent = load_file_as_binary_content(file_path)

    # pydantic-ai accepts list of content parts
    message_content = [prompt, binary_content]

    result: RunResult[EnrichmentOut] = agent.run_sync(message_content, deps=deps)
    # pydantic-ai 0.0.14+ uses .data attribute
    output = getattr(result, "data", getattr(result, "output", result))
    return output.markdown.strip()
