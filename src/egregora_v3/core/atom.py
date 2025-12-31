"""Atom feed serialization for Egregora V3."""

import jinja2
from pathlib import Path
from xml.etree.ElementTree import register_namespace

from egregora_v3.core.types import Feed

# --- XML Configuration ---

# Register namespaces globally to ensure pretty prefixes in all XML output
# This is a module-level side effect, but necessary for clean Atom feeds.
try:
    register_namespace("", "http://www.w3.org/2005/Atom")
    register_namespace("thr", "http://purl.org/syndication/thread/1.0")
except Exception:  # pragma: no cover
    # Best effort registration; may fail in some environments or if already registered
    pass


def feed_to_xml_string(feed: Feed) -> str:
    """Serialize a Feed object to an Atom XML string."""
    template_dir = Path(__file__).parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=True
    )
    template = env.get_template("atom.xml.jinja")
    return template.render(feed=feed)
