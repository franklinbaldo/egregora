"""Tests for V3 Core Types and Atom Serialization."""

from datetime import UTC, datetime
from pathlib import Path

from egregora_v3.core.types import Author, Document, DocumentType, Feed, Link
from egregora_v3.infra.sinks.atom import AtomSink


def test_feed_to_xml_serialization(tmp_path: Path):
    """Test that a Feed can be serialized to valid Atom XML."""
    entry = Document(
        id="test-post",
        doc_type=DocumentType.POST,
        title="Test Post",
        content="Hello World",
        updated=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        internal_metadata={"slug": "test-post"},
    )
    entry.content_type = "text/markdown"
    entry.authors = [Author(name="Test Author", email="test@example.com")]
    entry.published = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    feed = Feed(
        id="urn:uuid:12345",
        title="Test Feed",
        updated=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        entries=[entry],
        authors=[Author(name="Feed Author")],
        links=[Link(href="http://example.com/feed", rel="self")],
    )

    output_path = tmp_path / "feed.xml"
    sink = AtomSink(output_path)
    sink.publish(feed)
    xml_output = output_path.read_text(encoding="utf-8")

    # Basic assertions
    assert '<?xml version=\'1.0\' encoding=\'UTF-8\'?>' in xml_output
    assert '<feed xmlns="http://www.w3.org/2005/Atom"' in xml_output
    assert '<title>Test Feed</title>' in xml_output
    assert '<id>urn:uuid:12345</id>' in xml_output
    assert '<name>Feed Author</name>' in xml_output

    # Entry assertions
    assert '<entry>' in xml_output
    assert '<title>Test Post</title>' in xml_output
    assert '<id>test-post</id>' in xml_output
    assert '<content type="text/markdown"><p>Hello World</p>\n</content>' in xml_output
    # Check for document type category
    assert 'term="post"' in xml_output
    assert 'scheme="https://egregora.app/schema#doc_type"' in xml_output


def test_document_semantic_identity():
    """Test that Document enforces semantic identity (slug-based ID)."""
    doc = Document(
        doc_type=DocumentType.POST,
        title="  My Semantic Title  ",
        content="Content",
        updated=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        # No slug provided, should derive from title
    )

    assert doc.id == "my-semantic-title"
    assert doc.internal_metadata["slug"] == "my-semantic-title"

    # Explicit slug
    doc2 = Document(
        doc_type=DocumentType.POST,
        title="Title",
        content="Content",
        id="explicit-slug",
        updated=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        internal_metadata={"slug": "explicit-slug"},
    )
    assert doc2.id == "explicit-slug"
