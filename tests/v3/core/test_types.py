import xml.etree.ElementTree as ET
from datetime import datetime, UTC

import pytest

from egregora_v3.core.types import Author, Document, DocumentType, documents_to_feed


def test_document_create_with_id_override():
    """'id_override' should always take precedence for the document ID."""
    doc = Document.create(
        content="test content",
        doc_type=DocumentType.NOTE,
        title="Test Note",
        id_override="explicit-id-123",
        slug="a-slug",
    )
    assert doc.id == "explicit-id-123"
    assert doc.slug == "a-slug"


def test_document_create_generates_slug_from_title():
    """If no slug is provided, it should be generated from the title and stored in metadata."""
    doc = Document.create(
        content="test content",
        doc_type=DocumentType.POST,
        title="  A Title With Spaces  ",
    )
    # The ID is now a UUID, not the slug
    assert doc.id != "a-title-with-spaces"
    assert len(doc.id) == 36
    # The slug is stored in metadata
    assert doc.slug == "a-title-with-spaces"


def test_document_create_fallback_to_uuid_when_no_id_override():
    """If no id_override is given, a stable content-based UUID should be generated."""
    doc = Document.create(
        content="some unique content",
        doc_type=DocumentType.NOTE,
        title="A valid title",
    )
    # Expecting a UUIDv5
    assert len(doc.id) == 36
    assert doc.slug == "a-valid-title"


def test_document_create_no_slug_for_empty_title():
    """If the title is empty or whitespace, the slug should be None."""
    doc = Document.create(
        content="test content",
        doc_type=DocumentType.NOTE,
        title=" ",
    )
    assert doc.slug is None


def test_document_create_content_uuid_is_stable():
    """Content-based UUIDs should be deterministic."""
    doc1 = Document.create(content="stable content", doc_type=DocumentType.NOTE, title="t")
    doc2 = Document.create(content="stable content", doc_type=DocumentType.NOTE, title="t")
    doc3 = Document.create(content="different content", doc_type=DocumentType.NOTE, title="t")
    assert doc1.id == doc2.id
    assert doc1.id != doc3.id


def test_feed_to_xml_produces_valid_atom_feed():
    """It should generate a valid Atom 1.0 XML string."""
    # Arrange
    doc = Document.create(
        id_override="test-doc-1",
        title="My First Post",
        content="Hello, world!",
        doc_type=DocumentType.POST,
    )
    doc.published = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    doc.authors = [Author(name="Jules")]

    feed = documents_to_feed(
        docs=[doc],
        feed_id="urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6",
        title="My Test Feed",
        authors=[Author(name="Admin")],
    )

    # Act
    xml_output = feed.to_xml()

    # Assert
    assert isinstance(xml_output, str)
    assert "<?xml version='1.0' encoding='utf-8'?>" in xml_output

    # Try parsing the XML to ensure it's well-formed
    try:
        root = ET.fromstring(xml_output)
        # Check for Atom namespace
        assert root.tag == "{http://www.w3.org/2005/Atom}feed"

        # Check for required feed elements
        assert root.find("{http://www.w3.org/2005/Atom}title").text == "My Test Feed"
        assert root.find("{http://www.w3.org/2005/Atom}id").text == "urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6"

        # Check for entry
        entry = root.find("{http://www.w3.org/2005/Atom}entry")
        assert entry is not None
        assert entry.find("{http://www.w3.org/2005/Atom}title").text == "My First Post"
        assert entry.find("{http://www.w3.org/2005/Atom}id").text == "test-doc-1"
        assert entry.find("{http://www.w3.org/2005/Atom}content").text == "Hello, world!"
        assert entry.find("{http://www.w3.org/2005/Atom}published").text == "2024-01-01T12:00:00Z"

    except ET.ParseError as e:
        pytest.fail(f"Feed.to_xml() produced invalid XML: {e}\\nOutput was:\\n{xml_output}")
