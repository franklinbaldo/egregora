"""Tests for V3 Core Types and Atom Serialization."""

from datetime import UTC, datetime

from egregora_v3.core.atom import feed_to_xml_string
from egregora_v3.core.types import Author, Document, DocumentStatus, DocumentType, Entry, Feed, Link


def test_feed_to_xml_serialization():
    """Test that a Feed can be serialized to valid Atom XML."""
    entry = Document(
        doc_type=DocumentType.POST,
        title="Test Post",
        content="Hello World",
        internal_metadata={"slug": "test-post"},
    )
    # The filter normalizes "text/markdown" -> "text" or "html".
    # Let's check filters.py: "text/markdown" -> "text"
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

    xml_output = feed_to_xml_string(feed)

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
    # The filter converts "text/markdown" to "text"
    assert '<content type="text">Hello World</content>' in xml_output
    # Check for document type category
    assert 'term="post"' in xml_output
    assert 'scheme="https://egregora.app/schema#doc_type"' in xml_output
