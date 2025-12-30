from pathlib import Path

from egregora_v3.core.types import Feed


class AtomSink:
    """A sink for writing Atom feeds to XML files."""

    def __init__(self, output_path: Path):
        self.output_path = output_path

    def publish(self, feed: Feed):
        """Render the feed using Feed.to_xml() and write it to disk."""
        xml_content = feed.to_xml()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(xml_content, encoding="utf-8")
