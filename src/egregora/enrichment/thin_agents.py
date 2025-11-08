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
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

from egregora.enrichment.agents import load_file_as_binary_content

if TYPE_CHECKING:
    from pydantic_ai.result import RunResult

logger = logging.getLogger(__name__)

# --- Typed output for pydantic-ai to parse ---


class EnrichmentOut(BaseModel):
    """Structured output for enrichment agents."""

    markdown: str


# --- Simple system prompts (inline, not Jinja2) ---

URL_SYSTEM = """You write brief, neutral, useful Markdown summaries of URLs.
Return only the final Markdown content, no preamble, no code fences.
Focus on what the content is about and why it might be relevant."""

MEDIA_SYSTEM = """You describe media files succinctly in Markdown.
Return only the final Markdown content, no preamble, no code fences.
Be objective and descriptive. If it's a meme, mention what situations it's good for."""


def make_url_agent(model_name: str) -> Agent[None, EnrichmentOut]:
    """Create a minimal URL enrichment agent.

    Args:
        model_name: Pydantic-AI model string (e.g., "google-gla:gemini-flash-latest")

    Returns:
        Configured pydantic-ai Agent for URL enrichment

    """
    return Agent[None, EnrichmentOut](
        model=model_name,
        system_prompt=URL_SYSTEM,
        output_type=EnrichmentOut,
    )


def make_media_agent(model_name: str) -> Agent[None, EnrichmentOut]:
    """Create a minimal media enrichment agent.

    Args:
        model_name: Pydantic-AI model string (e.g., "google-gla:gemini-flash-latest")

    Returns:
        Configured pydantic-ai Agent for media enrichment

    """
    return Agent[None, EnrichmentOut](
        model=model_name,
        system_prompt=MEDIA_SYSTEM,
        output_type=EnrichmentOut,
    )


# --- Single-call helpers ---


def run_url_enrichment(agent: Agent[None, EnrichmentOut], url: str | AnyUrl) -> str:
    """Run URL enrichment with a single agent call.

    Args:
        agent: Configured URL enrichment agent
        url: URL to enrich

    Returns:
        Markdown content describing the URL

    Raises:
        Exception: If agent call fails (let errors propagate)

    """
    url_str = str(url)
    prompt = f"Summarize what this URL is about in 1-2 sentences.\nURL: {url_str}"
    result: RunResult[EnrichmentOut] = agent.run_sync(prompt)
    # pydantic-ai 0.0.14+ uses .data attribute
    output = getattr(result, "data", getattr(result, "output", result))
    return output.markdown.strip()


def run_media_enrichment(
    agent: Agent[None, EnrichmentOut],
    file_path: Path,
    mime_hint: str | None = None,
) -> str:
    """Run media enrichment with a single agent call.

    Args:
        agent: Configured media enrichment agent
        file_path: Path to media file
        mime_hint: Optional MIME type hint (e.g., "image", "video")

    Returns:
        Markdown content describing the media

    Raises:
        Exception: If agent call fails (let errors propagate)

    """
    desc = "Describe this media file in 2-3 sentences, highlighting what a reader would learn by viewing it."
    hint_text = f" ({mime_hint})" if mime_hint else ""
    prompt = f"{desc}\nFILE: {file_path.name}{hint_text}"

    # Load file as BinaryContent for vision models
    binary_content: BinaryContent = load_file_as_binary_content(file_path)

    # pydantic-ai accepts list of content parts
    message_content = [prompt, binary_content]

    result: RunResult[EnrichmentOut] = agent.run_sync(message_content)
    # pydantic-ai 0.0.14+ uses .data attribute
    output = getattr(result, "data", getattr(result, "output", result))
    return output.markdown.strip()
