import pytest
from datetime import datetime, UTC
from uuid import uuid4

from egregora.data_primitives.document import Document, DocumentType
from egregora.metadata.minimum import ensure_minimum_metadata

MINIMUM_METADATA_KEYS = [
    "title",
    "slug",
    "date",
    "updated",
    "summary",
    "tags",
    "categories",
    "authors",
    "draft",
    "type",
    "doc_id",
    "source",
]


@pytest.mark.parametrize("doc_type", list(DocumentType))
def test_ensure_minimum_metadata_adds_missing_keys(doc_type):
    """Tests that all required metadata keys are added to a document."""
    slug = f"test-{doc_type.value}"
    doc = Document(
        id=str(uuid4()),
        content="Test content",
        type=doc_type,
        created_at=datetime.now(UTC),
        metadata={"slug": slug},
    )
    normalized_doc = ensure_minimum_metadata(doc)
    metadata = normalized_doc.metadata

    for key in MINIMUM_METADATA_KEYS:
        assert key in metadata

    assert metadata["type"] == doc_type.value
    assert metadata["slug"] == slug


def test_ensure_minimum_metadata_preserves_existing_values():
    """Tests that existing metadata values are not overwritten."""
    original_metadata = {
        "title": "Original Title",
        "summary": "Original Summary",
        "tags": ["original_tag"],
        "custom_key": "custom_value",
        "slug": "original-slug",
    }

    doc = Document(
        id=str(uuid4()),
        content="Test content",
        type=DocumentType.POST,
        created_at=datetime.now(UTC),
        metadata=original_metadata,
    )

    normalized_doc = ensure_minimum_metadata(doc)
    normalized_metadata = normalized_doc.metadata

    assert normalized_metadata["title"] == "Original Title"
    assert normalized_metadata["summary"] == "Original Summary"
    assert normalized_metadata["tags"] == ["original_tag"]
    assert normalized_metadata["custom_key"] == "custom_value"
    assert "date" in normalized_metadata  # Ensure defaults are still added


def test_ensure_minimum_metadata_handles_none_values():
    """Tests that metadata with None values is handled correctly."""
    doc_with_none = Document(
        id=str(uuid4()),
        content="Test content",
        type=DocumentType.POST,
        created_at=datetime.now(UTC),
        metadata={"title": None, "slug": "test-slug"},
    )
    normalized_doc = ensure_minimum_metadata(doc_with_none)
    # Depending on desired behavior, title could be a fallback or empty string.
    # For now, let's assume it should receive a fallback.
    assert normalized_doc.metadata["title"] is not None
    assert isinstance(normalized_doc.metadata["title"], str)
