"""Rendering utilities for V3 core types."""

from markdown_it import MarkdownIt

# --- Markdown Renderer ---
_md = MarkdownIt("commonmark", {"html": True})


def render_html(content: str | None) -> str | None:
    """Render markdown content to HTML.

    Returns None if content is None or empty.
    """
    if content:
        return _md.render(content).strip()
    return None
