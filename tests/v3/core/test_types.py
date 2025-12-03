import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError
from egregora_v3.core.types import Document, DocumentType, FeedItem

def test_feed_item_immutability():
    msg = FeedItem(
        id=uuid.uuid4(),
        timestamp=datetime.now(),
        source="User A",
        content="Hello world"
    )

    with pytest.raises(ValidationError):
        msg.content = "New content"

def test_document_create_factory():
    content = "# Hello"
    doc = Document.create(content=content, doc_type=DocumentType.POST)

    assert doc.content == content
    assert doc.type == DocumentType.POST
    assert isinstance(doc.id, uuid.UUID)

def test_document_content_addressed_id():
    content = "Same Content"
    doc1 = Document.create(content=content, doc_type=DocumentType.POST)
    doc2 = Document.create(content=content, doc_type=DocumentType.POST)
    doc3 = Document.create(content=content, doc_type=DocumentType.PROFILE)

    assert doc1.id == doc2.id
    assert doc1.id != doc3.id

def test_document_immutability():
    doc = Document.create(content="Test", doc_type=DocumentType.POST)
    with pytest.raises(ValidationError):
        doc.content = "Changed"

def test_document_types_exist():
    assert DocumentType.POST == "post"
    assert DocumentType.PROFILE == "profile"
    assert DocumentType.JOURNAL == "journal"
    assert DocumentType.ENRICHMENT == "enrichment"
    assert DocumentType.MEDIA == "media"
