
import os
from datetime import datetime, UTC
from pathlib import Path
import pytest
from egregora_v3.core.types import Feed, Document, DocumentType, Author, Link
from egregora_v3.infra.sinks.atom import AtomSink

@pytest.fixture
def sample_feed():
    """Provides a sample Feed object for testing."""
    doc1 = Document(
        id="doc1",
        title="Test Post 1",
        content="This is the content of the first post.",
        doc_type=DocumentType.POST,
        updated=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
        authors=[Author(name="Author One")],
        links=[Link(href="/post/1")],
    )
    doc2 = Document(
        id="doc2",
        title="Test Post 2",
        content="This is the **Markdown** content.",
        doc_type=DocumentType.POST,
        updated=datetime(2023, 1, 2, 12, 0, 0, tzinfo=UTC),
        authors=[Author(name="Author Two")],
        links=[Link(href="/post/2")],
    )
    return Feed.from_documents(
        docs=[doc1, doc2],
        feed_id="test-feed",
        title="My Test Feed",
        authors=[Author(name="Feed Author")],
    )

def test_atom_sink_renders_feed_to_xml(tmp_path: Path, sample_feed: Feed):
    """
    Tests that the AtomSink can render a Feed object to an XML file.
    """
    # GIVEN
    output_path = tmp_path / "atom.xml"
    sink = AtomSink(output_path)

    # WHEN
    sink.publish(sample_feed)

    # THEN
    assert output_path.exists()
    xml_content = output_path.read_text()

    assert "<feed" in xml_content
    assert "<title>My Test Feed</title>" in xml_content
    assert "<entry>" in xml_content
    assert "<title>Test Post 2</title>" in xml_content # Most recent
    assert "<p>This is the <strong>Markdown</strong> content.</p>" in xml_content
    assert "<updated>2023-01-02T12:00:00+00:00</updated>" in xml_content
    assert "<id>doc2</id>" in xml_content
