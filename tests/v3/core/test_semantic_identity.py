"""Tests for semantic identity with slugs."""

from egregora_v3.core.types import Document, DocumentType


def test_id_override_takes_precedence():
    """id_override should take precedence over slug and UUID."""
    doc = Document.create(
        content="Content",
        doc_type=DocumentType.POST,
        title="Test",
        slug="my-slug",
        id_override="custom-id-123",
    )
    assert doc.id == "custom-id-123"
    assert doc.internal_metadata.get("slug") == "my-slug"


def test_slug_as_id():
    """A provided slug should be used as the ID."""
    doc = Document.create(content="Content", doc_type=DocumentType.POST, title="Test", slug="my-post")
    assert doc.id == "my-post"
    assert doc.internal_metadata.get("slug") == "my-post"


def test_slug_derived_from_title():
    """If no slug is provided, it should be derived from the title."""
    doc = Document.create(content="Content", doc_type=DocumentType.POST, title="My Awesome Post")
    assert doc.id == "my-awesome-post"
    assert doc.internal_metadata.get("slug") == "my-awesome-post"


def test_uuid_fallback_for_empty_slug_and_title():
    """If slug and title are empty, a UUID should be generated."""
    doc = Document.create(content="Content", doc_type=DocumentType.POST, title="", slug="")
    # Should be a UUID
    assert len(doc.id) == 36


def test_content_addressed_uuid_is_stable():
    """Content-based UUIDs should be stable for the same inputs."""
    doc1 = Document.create(content="Same content", doc_type=DocumentType.NOTE, title="")
    doc2 = Document.create(content="Same content", doc_type=DocumentType.NOTE, title="")
    assert doc1.id == doc2.id


def test_uuid_differs_by_doc_type():
    """UUIDs should differ if doc_type is different."""
    doc1 = Document.create(content="Same content", doc_type=DocumentType.POST, title="")
    doc2 = Document.create(content="Same content", doc_type=DocumentType.NOTE, title="")
    assert doc1.id != doc2.id


def test_uuid_differs_by_slug():
    """UUIDs should differ if slug is different."""
    doc1 = Document.create(content="Same content", doc_type=DocumentType.POST, title="", slug="slug-1")
    doc2 = Document.create(content="Same content", doc_type=DocumentType.POST, title="", slug="slug-2")
    # Slugs take precedence
    assert doc1.id != doc2.id
