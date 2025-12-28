
from pathlib import Path
import jinja2

from egregora_v3.core.filters import format_datetime
from egregora_v3.core.types import Feed


class AtomSink:
    """A sink for writing Atom feeds to XML files."""

    def __init__(self, output_path: Path):
        self.output_path = output_path

        env = jinja2.Environment(
            loader=jinja2.PackageLoader("egregora_v3.infra.sinks", "templates"),
            autoescape=jinja2.select_autoescape(['xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters['iso_utc'] = format_datetime
        self._jinja_env = env

    def publish(self, feed: Feed):
        """Renders the feed to XML and writes it to the output path."""
        template = self._jinja_env.get_template("atom.xml.jinja")
        xml_content = template.render(feed=feed).strip()
        self.output_path.write_text(xml_content)
