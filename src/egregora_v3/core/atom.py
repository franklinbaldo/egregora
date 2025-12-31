"""Atom feed serialization for Egregora V3."""

import jinja2
from pathlib import Path

from egregora_v3.core.types import Feed


def feed_to_xml_string(feed: Feed) -> str:
    """Serialize a Feed object to an Atom XML string."""
    template_dir = Path(__file__).parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=True
    )
    template = env.get_template("atom.xml.jinja")
    return template.render(feed=feed)
