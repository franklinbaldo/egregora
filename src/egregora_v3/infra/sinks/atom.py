
from pathlib import Path
import jinja2
from markdown_it import MarkdownIt
from datetime import datetime, UTC

from egregora_v3.core.filters import format_datetime
from egregora_v3.core.types import Feed

def content_type_filter(value: str | None) -> str:
    """Jinja2 filter to provide a default content type."""
    return value if value is not None else "html"

class AtomSink:
    """A sink for writing Atom feeds to XML files."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self._jinja_env = self._setup_jinja_env()
        self._md = MarkdownIt("commonmark", {"html": True})

    def _setup_jinja_env(self) -> jinja2.Environment:
        """Configures the Jinja2 environment."""
        env = jinja2.Environment(
            loader=jinja2.PackageLoader("egregora_v3.infra.sinks", "templates"),
            autoescape=jinja2.select_autoescape(['xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters['iso_utc'] = format_datetime
        env.filters['content_type'] = content_type_filter
        return env

    def publish(self, feed: Feed):
        """Renders the feed to XML and writes it to the output path."""
        template = self._jinja_env.get_template("atom.xml.jinja")
        xml_content = template.render(feed=feed).strip()
        self.output_path.write_text(xml_content)
