"""Tests for V3 Core Types and Atom Serialization."""

from datetime import UTC, datetime

from egregora_v3.core.types import Author, Document, DocumentStatus, DocumentType, Entry, Feed, Link


def test_document_semantic_identity():
    """Test that Document enforces semantic identity (slug-based ID)."""
    doc = Document(
        doc_type=DocumentType.POST,
        title="  My Semantic Title  ",
        content="Content",
        # No slug provided, should derive from title
    )

    assert doc.id == "my-semantic-title"
    assert doc.internal_metadata["slug"] == "my-semantic-title"

    # Explicit slug
    doc2 = Document(
        doc_type=DocumentType.POST,
        title="Title",
        content="Content",
        internal_metadata={"slug": "explicit-slug"}
    )
    assert doc2.id == "explicit-slug"
