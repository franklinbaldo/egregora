
import tempfile
from pathlib import Path
from datetime import datetime, UTC
from freezegun import freeze_time
from egregora_v3.core.types import Feed, Entry, Author
from egregora_v3.infra.sinks.atom import AtomSink

@freeze_time("2025-12-25 12:00:00 UTC")
def test_atom_sink_renders_markdown_content():
    """
    Locking Test: Confirms the AtomSink correctly renders markdown to HTML.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "feed.xml"
        sink = AtomSink(output_path)

        entry = Entry(
            id="test-entry",
            title="Markdown Test",
            updated=datetime.now(UTC),
            content="*Hello*, **World**!",
            content_type="text/markdown",
        )
        feed = Feed(
            id="test-feed",
            title="Test Feed",
            updated=datetime.now(UTC),
            entries=[entry],
            authors=[Author(name="Test Author")],
        )

        sink.publish(feed)

        assert output_path.exists()
        xml_content = output_path.read_text()

        # Check that the markdown was rendered to HTML
        assert "<p><em>Hello</em>, <strong>World</strong>!</p>" in xml_content
        # Check that the original markdown is gone
        assert "*Hello*, **World**!" not in xml_content
        # Check for Atom structure
        assert "<feed xmlns=" in xml_content
        assert "<entry>" in xml_content
        assert "<title>Markdown Test</title>" in xml_content
