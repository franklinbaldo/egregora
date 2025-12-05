from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError

from egregora_v3.core.types import Document, DocumentType, Entry, InReplyTo, documents_to_feed

# --- Entry Tests ---


def test_entry_validation():
    # Test valid entry
    entry = Entry(id="urn:uuid:1234", title="Test Entry", updated=datetime.now(UTC), content="Some content")
    assert entry.id == "urn:uuid:1234"
    assert entry.title == "Test Entry"

    # Test missing mandatory fields
    with pytest.raises(ValidationError):
        Entry(id="123")  # missing title and updated


# --- Document Tests ---


def test_document_create_factory():
    content = "# Hello"
    doc = Document.create(content=content, doc_type=DocumentType.POST, title="My Post")

    assert doc.content == content
    assert doc.doc_type == DocumentType.POST
    assert doc.title == "My Post"
    assert isinstance(doc.id, str)
    # Post is semantic, so ID should be slug-like
    assert doc.id == "my-post"


def test_document_content_addressed_id():
    content = "Same Content"
    doc1 = Document.create(content=content, doc_type=DocumentType.POST, title="Title")
    doc2 = Document.create(content=content, doc_type=DocumentType.POST, title="Title")
    doc3 = Document.create(content=content, doc_type=DocumentType.PROFILE, title="Title")

    assert doc1.id == doc2.id
    assert doc1.id != doc3.id


def test_document_semantic_identity_slug_derivation():
    # POST with title -> should derive slug
    doc = Document.create(content="Body", doc_type=DocumentType.POST, title="My Great Post")
    assert doc.slug == "my-great-post"
    assert doc.id == "my-great-post"

    # MEDIA with explicit slug
    doc_media = Document.create(content="Image", doc_type=DocumentType.MEDIA, title="Pic", slug="my-pic")
    assert doc_media.slug == "my-pic"
    assert doc_media.id == "my-pic"


def test_document_semantic_identity_fallback():
    # NOTE (non-semantic) -> no slug, UUID ID
    doc = Document.create(content="Note body", doc_type=DocumentType.NOTE, title="Just a note")
    assert doc.slug is None
    # ID should be UUIDv5
    assert len(doc.id) == 36

    # POST with empty title -> fallback to UUIDv5
    doc_empty = Document.create(content="Body", doc_type=DocumentType.POST, title="")
    assert doc_empty.slug is None
    assert len(doc_empty.id) == 36


def test_document_id_override():
    doc = Document.create(content="Body", doc_type=DocumentType.POST, title="Title", id_override="custom-id")
    assert doc.id == "custom-id"
    # Slug is still derived for semantic types
    assert doc.slug == "title"


def test_document_types_exist():
    assert DocumentType.POST == "post"
    assert DocumentType.PROFILE == "profile"
    assert DocumentType.NOTE == "note"
    assert DocumentType.RECAP == "recap"
    assert DocumentType.ENRICHMENT == "enrichment"


def test_searchable_flag():
    doc = Document.create(content="A", doc_type=DocumentType.POST, title="A", searchable=False)
    assert doc.searchable is False

    doc_default = Document.create(content="A", doc_type=DocumentType.POST, title="A")
    assert doc_default.searchable is True


# --- Feed Tests ---


def test_documents_to_feed():
    doc1 = Document.create(content="A", doc_type=DocumentType.NOTE, title="A")
    doc2 = Document.create(content="B", doc_type=DocumentType.NOTE, title="B")

    feed = documents_to_feed([doc1, doc2], feed_id="test-feed", title="Test Feed")

    assert feed.title == "Test Feed"
    assert len(feed.entries) == 2
    assert feed.updated >= doc1.updated
    assert feed.updated >= doc2.updated


def test_empty_feed():
    feed = documents_to_feed([], feed_id="empty", title="Empty")
    assert len(feed.entries) == 0
    assert isinstance(feed.updated, datetime)


def test_threading_support():
    parent = Document.create(content="Parent", doc_type=DocumentType.POST, title="P")
    reply = Document.create(
        content="Reply",
        doc_type=DocumentType.NOTE,
        title="R",
        in_reply_to=InReplyTo(ref=parent.id, type="text/markdown"),
    )

    assert reply.in_reply_to is not None
    assert reply.in_reply_to.ref == parent.id
    assert reply.in_reply_to.type == "text/markdown"

    # Test Feed XML Generation with Threading
    feed = documents_to_feed([reply], feed_id="test", title="Thread Test")
    xml = feed.to_xml()
    root = ET.fromstring(xml)
    entry = root.find("{http://www.w3.org/2005/Atom}entry")
    in_reply_to = entry.find("{http://purl.org/syndication/thread/1.0}in-reply-to")

    assert in_reply_to is not None
    assert in_reply_to.get("ref") == parent.id
    assert in_reply_to.get("type") == "text/markdown"
