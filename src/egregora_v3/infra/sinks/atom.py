from pathlib import Path

from egregora_v3.core.atom import feed_to_xml_string
from egregora_v3.core.types import Feed


class AtomSink:
    """A sink for writing Atom feeds to XML files."""

    def __init__(self, output_path: Path):
        self.output_path = output_path

    def publish(self, feed: Feed):
        """Renders the feed to XML and writes it to the output path."""
        xml_content = feed_to_xml_string(feed)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(xml_content)
