"""Atom XML Output Sink for publishing feeds as Atom XML files."""

from pathlib import Path

from egregora_v3.core.types import Feed


class AtomXMLOutputSink:
    """Publishes a Feed as an Atom XML file.

    Implements the OutputSink protocol by writing Feed.to_xml() to a file.
    """

    def __init__(self, output_path: Path) -> None:
        """Initialize the Atom XML output sink.

        Args:
            output_path: Path where the Atom XML file will be written

        """
        self.output_path = Path(output_path)

    def publish(self, feed: Feed) -> None:
        """Publish the feed as an Atom XML file.

        Args:
            feed: The Feed to publish

        Creates parent directories if they don't exist.
        Overwrites existing file if present.

        """
        # Create parent directories if needed
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate Atom XML
        xml_output = feed.to_xml()

        # Write to file
        self.output_path.write_text(xml_output, encoding="utf-8")
