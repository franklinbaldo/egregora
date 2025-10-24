"""Jinja2 template management for system prompts."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Jinja2 environment with auto-escaping disabled (we're generating prompts, not HTML)
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(enabled_extensions=()),  # Disable autoescaping
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_writer_prompt(
    date: str,
    markdown_table: str,
    active_authors: str,
    custom_instructions: str = "",
    markdown_features: str = "",
    profiles_context: str = "",
    rag_context: str = "",
) -> str:
    """
    Render the writer system prompt from Jinja template.

    Args:
        date: Period date (e.g., "2025-03-02")
        markdown_table: Messages formatted as markdown table
        active_authors: Comma-separated list of active author UUIDs
        custom_instructions: Optional custom writing instructions
        markdown_features: Optional markdown extensions info
        profiles_context: Optional author profiles context
        rag_context: Optional RAG context from similar posts

    Returns:
        Rendered prompt string
    """
    template = env.get_template("writer_system.jinja")
    return template.render(
        date=date,
        markdown_table=markdown_table,
        active_authors=active_authors,
        custom_instructions=custom_instructions,
        markdown_features=markdown_features,
        profiles_context=profiles_context,
        rag_context=rag_context,
    )


def render_url_enrichment_prompt(url: str) -> str:
    """
    Render URL enrichment prompt from Jinja template.

    Args:
        url: URL to describe

    Returns:
        Rendered prompt string
    """
    template = env.get_template("enricher_url.jinja")
    return template.render(url=url)


def render_media_enrichment_prompt() -> str:
    """
    Render media enrichment prompt from Jinja template.

    Returns:
        Rendered prompt string
    """
    template = env.get_template("enricher_media.jinja")
    return template.render()
