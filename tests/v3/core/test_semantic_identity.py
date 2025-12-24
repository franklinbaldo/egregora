
import uuid
import pytest

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


def test_random_uuid_fallback():
    """If slug and title are empty, a random UUID should be generated."""
    doc = Document.create(content="Content", doc_type=DocumentType.POST, title="", slug="")

    # Check if it's a valid UUID
    try:
        uuid.UUID(doc.id, version=4)
    except ValueError:
        pytest.fail(f"{doc.id} is not a valid UUIDv4")

def test_fallback_uuids_are_not_stable():
    """Fallback UUIDs should be random, not content-addressed."""
    doc1 = Document.create(content="Same content", doc_type=DocumentType.NOTE, title="")
    doc2 = Document.create(content="Same content", doc_type=DocumentType.NOTE, title="")
    assert doc1.id != doc2.id
