"""Tests for Atom XML feed export (RFC 4287)."""
from datetime import UTC, datetime
import xml.etree.ElementTree as ET

from egregora_v3.core.types import (
    Author,
    Category,
    Document,
    DocumentType,
    Entry,
    Feed,
    Link,
    documents_to_feed,
)


def test_feed_to_xml_basic():
    """Test basic Feed to Atom XML conversion."""
    feed = Feed(
        id="http://example.org/feed",
        title="Test Feed",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        authors=[Author(name="Alice", email="alice@example.org")],
        entries=[]
    )

    xml = feed.to_xml()

    # Check XML declaration (ElementTree uses single quotes)
    assert xml.startswith('<?xml version') and 'encoding' in xml[:50]
    assert '<feed xmlns="http://www.w3.org/2005/Atom">' in xml
    assert '<id>http://example.org/feed</id>' in xml
    assert '<title>Test Feed</title>' in xml
    assert '<author>' in xml
    assert '<name>Alice</name>' in xml


def test_feed_with_entries():
    """Test Feed with entries converts to valid Atom."""
    entry = Entry(
        id="entry-1",
        title="First Post",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        content="Hello World",
        published=datetime(2024, 12, 4, 10, 0, 0, tzinfo=UTC)
    )

    feed = Feed(
        id="http://example.org/feed",
        title="Test Feed",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        entries=[entry]
    )

    xml = feed.to_xml()

    assert '<entry>' in xml
    assert '<id>entry-1</id>' in xml
    assert '<title>First Post</title>' in xml
    assert '<content' in xml
    assert 'Hello World' in xml


def test_entry_with_links():
    """Test Entry with links (including enclosures)."""
    entry = Entry(
        id="entry-1",
        title="Photo Post",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        content="Check out this photo",
        links=[
            Link(
                rel="enclosure",
                href="http://example.org/photo.jpg",
                type="image/jpeg",
                length=245760
            ),
            Link(
                rel="alternate",
                href="http://example.org/posts/photo-post",
                type="text/html"
            )
        ]
    )

    feed = Feed(
        id="http://example.org/feed",
        title="Test Feed",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        entries=[entry]
    )

    xml = feed.to_xml()

    # Check for enclosure link (attribute order may vary)
    assert 'rel="enclosure"' in xml
    assert 'href="http://example.org/photo.jpg"' in xml
    assert 'type="image/jpeg"' in xml
    assert 'length="245760"' in xml


def test_entry_with_categories():
    """Test Entry with categories/tags."""
    entry = Entry(
        id="entry-1",
        title="Tagged Post",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        categories=[
            Category(term="python", label="Python"),
            Category(term="tdd", label="Test-Driven Development")
        ]
    )

    feed = Feed(
        id="http://example.org/feed",
        title="Test Feed",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        entries=[entry]
    )

    xml = feed.to_xml()

    assert '<category term="python"' in xml
    assert 'label="Python"' in xml
    assert '<category term="tdd"' in xml


def test_feed_parses_as_valid_xml():
    """Test that generated XML is valid and parseable."""
    doc = Document.create(
        content="Test content",
        doc_type=DocumentType.POST,
        title="Test Post"
    )

    feed = documents_to_feed(
        [doc],
        feed_id="http://example.org/feed",
        title="Test Feed",
        authors=[Author(name="Alice")]
    )

    xml = feed.to_xml()

    # Should parse without error
    root = ET.fromstring(xml)

    # Check namespace
    assert root.tag == "{http://www.w3.org/2005/Atom}feed"

    # Check required elements
    assert root.find("{http://www.w3.org/2005/Atom}id") is not None
    assert root.find("{http://www.w3.org/2005/Atom}title") is not None
    assert root.find("{http://www.w3.org/2005/Atom}updated") is not None


def test_datetime_formatting():
    """Test that datetimes are formatted as RFC 3339."""
    feed = Feed(
        id="http://example.org/feed",
        title="Test Feed",
        updated=datetime(2024, 12, 4, 15, 30, 45, tzinfo=UTC)
    )

    xml = feed.to_xml()

    # RFC 3339 format: 2024-12-04T15:30:45Z
    assert "2024-12-04T15:30:45Z" in xml or "2024-12-04T15:30:45+00:00" in xml


def test_content_type_handling():
    """Test different content types."""
    entry = Entry(
        id="entry-1",
        title="HTML Post",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        content="<p>HTML content</p>",
        content_type="text/html"
    )

    feed = Feed(
        id="http://example.org/feed",
        title="Test Feed",
        updated=datetime(2024, 12, 4, 12, 0, 0, tzinfo=UTC),
        entries=[entry]
    )

    xml = feed.to_xml()

    assert '<content type="text/html"' in xml or '<content type="html"' in xml
