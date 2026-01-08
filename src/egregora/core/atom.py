"""Atom feed serialization for Egregora V3."""

from pathlib import Path

import jinja2

from egregora.core.types import Feed


def _normalize_content_type(value: str | None) -> str:
    """Normalize content types to Atom-compatible values."""
    if not value:
        return "html"

    normalized = value.strip().lower()
    if normalized in {"text/html", "text/xhtml", "html", "xhtml"}:
        return "html"
    if normalized in {"text/markdown", "text/md", "markdown"}:
        return "text"

    return value


def feed_to_xml_string(feed: Feed) -> str:
    """Serialize a Feed object to an Atom XML string."""
    template_dir = Path(__file__).parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["atom_content_type"] = _normalize_content_type
    template = env.get_template("atom.xml.jinja")
    return template.render(feed=feed)
