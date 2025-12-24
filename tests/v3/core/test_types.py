from datetime import datetime
from uuid import UUID

import pytest

from egregora_v3.core.types import Author, Document, DocumentType, Feed, documents_to_feed


def test_document_create_with_explicit_id():
    """Verify that the provided `id` is always used."""
    doc = Document.create(
        id="explicit-id",
        content="Test content",
        doc_type=DocumentType.NOTE,
        title="My Note",
        slug="a-slug",
    )
    assert doc.id == "explicit-id"
    assert doc.slug == "a-slug"


def test_document_create_generates_slug_from_title():
    """Verify slug is generated from title if not provided."""
    doc = Document.create(
        id="another-id", content="Test", doc_type=DocumentType.POST, title="A Title Here"
    )
    assert doc.slug == "a-title-here"
    assert doc.id == "another-id"


def test_document_create_handles_no_slug():
    """Verify that documents can be created without a slug."""
    doc = Document.create(id="no-slug-id", content="Content", doc_type=DocumentType.NOTE, title="")
    assert doc.slug is None
    assert doc.id == "no-slug-id"


def test_feed_to_xml_basic():
    """Verify basic Atom XML generation."""
    doc = Document.create(
        id="test-doc",
        title="Test Doc",
        content="Hello",
        doc_type=DocumentType.NOTE,
    )
    feed = documents_to_feed([doc], feed_id="test-feed", title="My Test Feed")
    xml_output = feed.to_xml()

    assert "<?xml version='1.0' encoding='utf-8'?>" in xml_output
    assert '<feed xmlns="http://www.w3.org/2005/Atom">' in xml_output
    assert "<id>test-feed</id>" in xml_output
    assert "<title>My Test Feed</title>" in xml_output
    assert "<entry>" in xml_output
    assert "<id>test-doc</id>" in xml_output
    assert "<title>Test Doc</title>" in xml_output
    assert "<content>Hello</content>" in xml_output
    assert "</feed>" in xml_output
