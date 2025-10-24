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


def render_url_enrichment_detailed_prompt(
    url: str,
    original_message: str,
    sender_uuid: str,
    date: str,
    time: str,
) -> str:
    """
    Render detailed URL enrichment prompt from Jinja template.

    Args:
        url: URL to analyze
        original_message: Original message containing the URL
        sender_uuid: Author UUID
        date: Date string (YYYY-MM-DD)
        time: Time string (HH:MM)

    Returns:
        Rendered prompt string
    """
    template = env.get_template("enricher_url_detailed.jinja")
    return template.render(
        url=url,
        original_message=original_message,
        sender_uuid=sender_uuid,
        date=date,
        time=time,
    )


def render_media_enrichment_detailed_prompt(
    media_type: str,
    media_filename: str,
    original_message: str,
    sender_uuid: str,
    date: str,
    time: str,
) -> str:
    """
    Render detailed media enrichment prompt from Jinja template.

    Args:
        media_type: Type of media (image, video, audio)
        media_filename: Original filename
        original_message: Original message containing the media
        sender_uuid: Author UUID
        date: Date string (YYYY-MM-DD)
        time: Time string (HH:MM)

    Returns:
        Rendered prompt string
    """
    template = env.get_template("enricher_media_detailed.jinja")
    return template.render(
        media_type=media_type,
        media_filename=media_filename,
        original_message=original_message,
        sender_uuid=sender_uuid,
        date=date,
        time=time,
    )


def render_url_enrichment_file(
    url: str,
    date: str,
    time: str,
    sender_uuid: str,
    original_message: str,
    summary: str,
    context: str,
    key_takeaways: str,
    url_metadata: str,
) -> str:
    """
    Render URL enrichment markdown file from Jinja template.

    Args:
        url: The URL
        date: Date string (YYYY-MM-DD)
        time: Time string (HH:MM)
        sender_uuid: Author UUID
        original_message: Original message
        summary: Summary of URL content
        context: Contextual relevance
        key_takeaways: Key points
        url_metadata: URL metadata

    Returns:
        Rendered markdown file content
    """
    template = env.get_template("enrichment_url.jinja")
    return template.render(
        url=url,
        date=date,
        time=time,
        sender_uuid=sender_uuid,
        original_message=original_message,
        summary=summary,
        context=context,
        key_takeaways=key_takeaways,
        url_metadata=url_metadata,
    )


def render_media_enrichment_file(
    media_filename: str,
    media_type: str,
    media_path: str,
    date: str,
    time: str,
    sender_uuid: str,
    original_message: str,
    description: str,
    context: str,
    elements: str,
    relevance: str,
) -> str:
    """
    Render media enrichment markdown file from Jinja template.

    Args:
        media_filename: Original filename
        media_type: Type (image, video, audio)
        media_path: Relative path to media file
        date: Date string (YYYY-MM-DD)
        time: Time string (HH:MM)
        sender_uuid: Author UUID
        original_message: Original message
        description: Description of media
        context: Contextual relevance
        elements: Visual/audio elements
        relevance: Why it matters

    Returns:
        Rendered markdown file content
    """
    template = env.get_template("enrichment_media.jinja")
    return template.render(
        media_filename=media_filename,
        media_type=media_type,
        media_path=media_path,
        date=date,
        time=time,
        sender_uuid=sender_uuid,
        original_message=original_message,
        description=description,
        context=context,
        elements=elements,
        relevance=relevance,
    )
