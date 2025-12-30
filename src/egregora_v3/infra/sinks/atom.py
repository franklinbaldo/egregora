from pathlib import Path

from egregora_v3.core.types import Feed


class AtomSink:
    """A sink for writing Atom feeds to XML files."""

    def __init__(self, output_path: Path):
        self.output_path = output_path

    def publish(self, feed: Feed):
        """Renders the feed to XML and writes it to the output path."""
        # Ensure parent directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        xml_content = feed.to_xml()
        self.output_path.write_text(xml_content, encoding="utf-8")
