# tests/unit/metadata/test_publishable_metadata.py

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from egregora.data_primitives.document import Document, DocumentType
from egregora.metadata.publishable import PublishableMetadata


class TestPublishableMetadataDefaults:
    """Tests for default values in PublishableMetadata."""

    def test_summary_defaults_to_empty_string(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
        )
        assert meta.summary == ""

    def test_tags_defaults_to_empty_tuple(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
        )
        assert meta.tags == ()
        assert isinstance(meta.tags, tuple)

    def test_draft_defaults_to_false(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
        )
        assert meta.draft is False


class TestPublishableMetadataFromDocument:
    """Tests for creating PublishableMetadata from Document."""

    @pytest.fixture
    def sample_document(self) -> Document:
        return Document(
            content="# Test Post",
            type=DocumentType.POST,
            metadata={
                "title": "My Post Title",
                "slug": "my-post",
                "tags": ["python", "testing"],
            },
            created_at=datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        )

    def test_from_document_extracts_existing_metadata(
        self, sample_document: Document
    ) -> None:
        meta = PublishableMetadata.from_document(sample_document)

        assert meta.title == "My Post Title"
        assert meta.slug == "my-post"
        assert meta.tags == ("python", "testing")

    def test_from_document_uses_created_at_for_date(
        self, sample_document: Document
    ) -> None:
        meta = PublishableMetadata.from_document(sample_document)

        assert meta.date == "2025-06-15T10:00:00+00:00"

    def test_from_document_defaults_title_if_missing(self) -> None:
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={"slug": "test"},
        )

        meta = PublishableMetadata.from_document(doc)

        assert meta.title == "Untitled Post"

    def test_from_document_defaults_updated_to_date(self) -> None:
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={"slug": "test"},
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        meta = PublishableMetadata.from_document(doc)

        assert meta.updated == meta.date

    def test_from_document_preserves_extra_fields(self) -> None:
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={
                "slug": "test",
                "custom_field": "custom_value",
                "another_field": 123,
            },
        )

        meta = PublishableMetadata.from_document(doc)

        assert meta.extra["custom_field"] == "custom_value"
        assert meta.extra["another_field"] == 123

    @pytest.mark.parametrize("doc_type", list(DocumentType))
    def test_from_document_works_for_all_types(
        self, doc_type: DocumentType
    ) -> None:
        doc = Document(
            content="Content",
            type=doc_type,
            metadata={"slug": f"test-{doc_type.value}"},
        )

        meta = PublishableMetadata.from_document(doc)

        assert meta.doc_type == doc_type.value


class TestPublishableMetadataToDict:
    """Tests for serializing PublishableMetadata to dict."""

    def test_to_dict_includes_all_fields(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
            tags=("a", "b"),
            authors=("author-1",),
        )

        d = meta.to_dict()

        assert d["title"] == "Test"
        assert d["slug"] == "test"
        assert d["tags"] == ["a", "b"]  # Converts tuple to list
        assert d["authors"] == ["author-1"]

    def test_to_dict_merges_extra_fields(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
            extra={"custom": "value"},
        )

        d = meta.to_dict()

        assert d["custom"] == "value"

    def test_to_dict_omits_none_source_window(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
            source_window=None,
        )

        d = meta.to_dict()

        assert "source_window" not in d or d.get("source_window") is None


class TestPublishableMetadataImmutability:
    """Tests that PublishableMetadata is immutable."""

    def test_cannot_modify_fields(self) -> None:
        meta = PublishableMetadata(
            title="Test",
            slug="test",
            date="2025-01-15T10:00:00Z",
            updated="2025-01-15T10:00:00Z",
        )

        with pytest.raises(AttributeError):
            meta.title = "New Title"  # type: ignore
