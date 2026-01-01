"""Rendering utilities for V3 Documents."""

from markdown_it import MarkdownIt

from egregora_v3.core.types import Entry

# --- Markdown Renderer ---
_md = MarkdownIt("commonmark", {"html": True})


def render_html_content(entry: Entry) -> str | None:
    """Render markdown content to HTML."""
    if entry.content:
        return _md.render(entry.content).strip()
    return None
