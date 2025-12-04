import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from egregora_v3.core.types import Document, DocumentType, Entry, InReplyTo, documents_to_feed


def test_entry_validation():
    # Test valid entry
    entry = Entry(
        id="urn:uuid:1234",
        title="Test Entry",
        updated=datetime.now(UTC),
        content="Some content"
    )
    assert entry.id == "urn:uuid:1234"
    assert entry.title == "Test Entry"

    # Test missing mandatory fields
    with pytest.raises(ValidationError):
        Entry(id="123") # missing title and updated

def test_document_create_factory():
    content = "# Hello"
    doc = Document.create(content=content, doc_type=DocumentType.POST, title="My Post")

    assert doc.content == content
    assert doc.doc_type == DocumentType.POST
    assert doc.title == "My Post"
    assert isinstance(doc.id, str)
    # Check if id looks like a UUID
    uuid.UUID(doc.id)

def test_document_content_addressed_id():
    content = "Same Content"
    doc1 = Document.create(content=content, doc_type=DocumentType.POST, title="Title")
    doc2 = Document.create(content=content, doc_type=DocumentType.POST, title="Title")
    doc3 = Document.create(content=content, doc_type=DocumentType.PROFILE, title="Title")

    assert doc1.id == doc2.id
    assert doc1.id != doc3.id

def test_document_types_exist():
    assert DocumentType.POST == "post"
    assert DocumentType.PROFILE == "profile"
    assert DocumentType.NOTE == "note"
    assert DocumentType.RECAP == "recap"
    assert DocumentType.ENRICHMENT == "enrichment"

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
        in_reply_to=InReplyTo(ref=parent.id, type="text/markdown")
    )

    assert reply.in_reply_to is not None
    assert reply.in_reply_to.ref == parent.id
    assert reply.in_reply_to.type == "text/markdown"

def test_searchable_flag():
    doc = Document.create(content="A", doc_type=DocumentType.POST, title="A", searchable=False)
    assert doc.searchable is False

    doc_default = Document.create(content="A", doc_type=DocumentType.POST, title="A")
    assert doc_default.searchable is True
