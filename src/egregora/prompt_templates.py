"""Jinja2 template management for system prompts."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Prompts directory
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Jinja2 environment with auto-escaping disabled (we're generating prompts, not HTML)
env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    autoescape=select_autoescape(enabled_extensions=()),  # Disable autoescaping
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_writer_prompt(  # noqa: PLR0913
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


def render_media_enrichment_detailed_prompt(  # noqa: PLR0913
    media_type: str,
    media_filename: str,
    media_path: str,
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
        media_path: Relative path to media file
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
        media_path=media_path,
        original_message=original_message,
        sender_uuid=sender_uuid,
        date=date,
        time=time,
    )


def render_editor_prompt(
    post_content: str,
    doc_id: str,
    version: int,
    lines: dict[int, str],
    context: dict | None = None,
) -> str:
    """
    Render editor system prompt from Jinja template.

    Args:
        post_content: Full markdown content of the post
        doc_id: Document identifier (usually file path)
        version: Current document version
        lines: Line-indexed dictionary of post content
        context: Optional context (ELO, ranking comments, etc.)

    Returns:
        Rendered prompt string
    """
    template = env.get_template("editor_system.jinja")
    return template.render(
        post_content=post_content,
        doc_id=doc_id,
        version=version,
        lines=lines,
        context=context or {},
    )
