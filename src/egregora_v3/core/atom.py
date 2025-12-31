"""Atom feed serialization logic."""
from __future__ import annotations

from typing import TYPE_CHECKING
import jinja2
from pathlib import Path

if TYPE_CHECKING:
    from egregora_v3.core.types import Feed


def render_atom_feed(feed: "Feed") -> str:
    """Serialize the feed to an Atom XML string."""
    template_dir = Path(__file__).parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    def content_type_filter(content_type: str | None) -> str:
        """Jinja filter to normalize content type for Atom feed."""
        if not content_type:
            return "html"
        if "html" in content_type:
            return "html"
        if "xhtml" in content_type:
            return "xhtml"
        if "markdown" in content_type:
            return "text"
        return "text"

    env.filters['content_type'] = content_type_filter
    template = env.get_template("atom.xml.jinja")
    return template.render(feed=feed)
