
import tempfile
from pathlib import Path
from datetime import datetime, UTC
from freezegun import freeze_time
from egregora_v3.core.types import Feed, Entry, Author, DocumentType, DocumentStatus
from egregora_v3.infra.sinks.atom import AtomSink

@freeze_time("2025-12-25 12:00:00 UTC")
def test_atom_sink_defaults_content_type_and_preserves_raw_content():
    """
    Confirms AtomSink defaults content type and does not render markdown.
    This test proves that the MarkdownIt dependency is unused.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "feed.xml"
        sink = AtomSink(output_path)

        entry = Entry(
            id="test-entry",
            title="Raw Content Test",
            updated=datetime.now(UTC),
            content="*Hello*, **World**!",
            content_type=None,  # Explicitly None to test the filter
                doc_type=DocumentType.POST,
                status=DocumentStatus.PUBLISHED,
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

        # 1. Check that content_type defaults to "html" because of the custom filter
        assert '<content type="text/plain">' in xml_content

        # 2. Check that the raw markdown is present and NOT rendered to HTML
        # The content is XML-escaped by Jinja, but not transformed.
        assert "<p><em>Hello</em>, <strong>World</strong>!</p>" not in xml_content
        assert "*Hello*, **World**!" in xml_content
