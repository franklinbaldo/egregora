"""Tests for semantic identity with slugs (Phase 1.5)."""
import pytest
from egregora_v3.core.types import Document, DocumentType


def test_post_with_slug_uses_slug_as_id():
    """Posts with slugs should use the slug as their ID."""
    doc = Document.create(
        content="Hello World",
        doc_type=DocumentType.POST,
        title="My Post",
        slug="my-awesome-post"
    )

    assert doc.id == "my-awesome-post"
    assert doc.internal_metadata.get("slug") == "my-awesome-post"


def test_media_with_slug_uses_slug_as_id():
    """Media with slugs should use the slug as their ID."""
    doc = Document.create(
        content="Photo description",
        doc_type=DocumentType.MEDIA,
        title="Sunset Photo",
        slug="sunset-photo-2024"
    )

    assert doc.id == "sunset-photo-2024"


def test_profile_with_slug_uses_uuid():
    """Profiles should use UUID even with slugs (immutable identity)."""
    doc = Document.create(
        content="Profile bio",
        doc_type=DocumentType.PROFILE,
        title="Alice",
        slug="alice-profile"
    )

    # Profile should NOT use slug as ID (UUID for immutable types)
    assert doc.id != "alice-profile"
    assert len(doc.id) == 36  # UUID length
    assert doc.internal_metadata.get("slug") == "alice-profile"


def test_post_without_slug_uses_title_slug():
    """Posts without explicit slug should derive it from the title."""
    doc = Document.create(
        content="Hello World",
        doc_type=DocumentType.POST,
        title="My Awesome Post",
    )

    assert doc.id == "my-awesome-post"
    assert doc.internal_metadata.get("slug") == "my-awesome-post"


def test_enrichment_uses_uuid_not_slug():
    """Enrichments are immutable, should always use UUID."""
    doc = Document.create(
        content="Enrichment data",
        doc_type=DocumentType.ENRICHMENT,
        title="Image Analysis",
        slug="should-not-be-used"
    )

    assert doc.id != "should-not-be-used"
    assert len(doc.id) == 36  # UUID


def test_slug_sanitization():
    """Slugs should be sanitized to URL-safe format."""
    doc = Document.create(
        content="Content",
        doc_type=DocumentType.POST,
        title="Test",
        slug="My Awesome Post!!!"
    )

    # Should be sanitized by slugify
    assert doc.id == "my-awesome-post"
    assert doc.internal_metadata.get("slug") == "my-awesome-post"


def test_empty_slug_fallback_to_uuid():
    """Empty slugs should fall back to UUID."""
    doc = Document.create(
        content="Content",
        doc_type=DocumentType.POST,
        title="Test",
        slug=""
    )

    # Should use UUID since slug is empty
    assert len(doc.id) == 36


def test_id_override_takes_precedence():
    """id_override should take precedence over slug."""
    doc = Document.create(
        content="Content",
        doc_type=DocumentType.POST,
        title="Test",
        slug="my-slug",
        id_override="custom-id-123"
    )

    assert doc.id == "custom-id-123"
    assert doc.internal_metadata.get("slug") == "my-slug"


def test_content_addressed_id_for_no_slug():
    """Documents without slugs should get content-addressed UUIDs."""
    doc1 = Document.create(
        content="Same content",
        doc_type=DocumentType.NOTE,
        title="Note 1"
    )

    doc2 = Document.create(
        content="Same content",
        doc_type=DocumentType.NOTE,
        title="Note 2"
    )

    # Same content + same type = same ID
    assert doc1.id == doc2.id


def test_different_doc_types_different_ids():
    """Same content but different doc_type should have different IDs."""
    content = "Same content"

    post = Document.create(content, DocumentType.POST, "Title")
    note = Document.create(content, DocumentType.NOTE, "Title")

    assert post.id != note.id


def test_slug_stored_in_metadata():
    """Slug should be stored in internal_metadata."""
    doc = Document.create(
        content="Content",
        doc_type=DocumentType.POST,
        title="Test",
        slug="test-post"
    )

    assert doc.internal_metadata["slug"] == "test-post"


def test_long_slug_truncated():
    """Very long slugs should be truncated."""
    long_slug = "a" * 100

    doc = Document.create(
        content="Content",
        doc_type=DocumentType.POST,
        title="Test",
        slug=long_slug
    )

    # slugify should truncate to max_len=60
    assert len(doc.id) <= 60
