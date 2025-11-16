"""Tests for Document abstraction."""

from datetime import UTC, datetime

import pytest

from egregora.data_primitives.document import Document, DocumentCollection, DocumentType


class TestDocumentIdentity:
    """Tests for content-addressed document identity."""

    def test_same_content_produces_same_id(self):
        """Same content should produce same document ID (deduplication)."""
        doc1 = Document(content="Hello, world!", type=DocumentType.POST)
        doc2 = Document(content="Hello, world!", type=DocumentType.POST)

        assert doc1.document_id == doc2.document_id

    def test_different_content_produces_different_id(self):
        """Different content should produce different document IDs."""
        doc1 = Document(content="Hello, world!", type=DocumentType.POST)
        doc2 = Document(content="Goodbye, world!", type=DocumentType.POST)

        assert doc1.document_id != doc2.document_id

    def test_document_id_is_deterministic(self):
        """Document ID should be deterministic across multiple creations."""
        content = "Test content for determinism"

        ids = {Document(content=content, type=DocumentType.POST).document_id for _ in range(10)}

        assert len(ids) == 1, "Document ID should be deterministic"

    def test_document_id_is_uuid_format(self):
        """Document ID should be a valid UUID string."""
        doc = Document(content="Test", type=DocumentType.POST)

        # UUID format: 8-4-4-4-12 characters
        assert len(doc.document_id) == 36
        assert doc.document_id.count("-") == 4

    def test_metadata_does_not_affect_id(self):
        """Metadata changes should not affect document ID (only content matters)."""
        doc1 = Document(
            content="Same content",
            type=DocumentType.POST,
            metadata={"title": "Title 1"},
        )
        doc2 = Document(
            content="Same content",
            type=DocumentType.POST,
            metadata={"title": "Title 2"},
        )

        assert doc1.document_id == doc2.document_id

    def test_type_does_not_affect_id(self):
        """Document type should not affect ID (only content)."""
        content = "Same content"
        doc1 = Document(content=content, type=DocumentType.POST)
        doc2 = Document(content=content, type=DocumentType.PROFILE)

        assert doc1.document_id == doc2.document_id


class TestDocumentCreation:
    """Tests for document creation and initialization."""

    def test_minimal_document_creation(self):
        """Can create document with only content and type."""
        doc = Document(content="Hello", type=DocumentType.POST)

        assert doc.content == "Hello"
        assert doc.type == DocumentType.POST
        assert doc.metadata == {}
        assert doc.parent_id is None
        assert doc.source_window is None
        assert doc.suggested_path is None

    def test_document_with_metadata(self):
        """Can create document with metadata."""
        metadata = {"title": "My Post", "date": "2025-01-10", "author": "Alice"}
        doc = Document(
            content="Post content",
            type=DocumentType.POST,
            metadata=metadata,
        )

        assert doc.metadata == metadata

    def test_document_with_parent(self):
        """Can create document with parent relationship."""
        doc = Document(
            content="Enrichment",
            type=DocumentType.ENRICHMENT_URL,
            parent_id="parent-doc-id",
        )

        assert doc.parent_id == "parent-doc-id"

    def test_document_with_all_fields(self):
        """Can create document with all fields populated."""
        now = datetime.now(UTC)
        doc = Document(
            content="Full document",
            type=DocumentType.POST,
            metadata={"title": "Test"},
            parent_id="parent-id",
            created_at=now,
            source_window="2025-01-10",
            suggested_path="posts/test.md",
        )

        assert doc.content == "Full document"
        assert doc.type == DocumentType.POST
        assert doc.metadata == {"title": "Test"}
        assert doc.parent_id == "parent-id"
        assert doc.created_at == now
        assert doc.source_window == "2025-01-10"
        assert doc.suggested_path == "posts/test.md"

    def test_document_is_frozen(self):
        """Document should be immutable (frozen dataclass)."""
        doc = Document(content="Test", type=DocumentType.POST)

        with pytest.raises(AttributeError):
            doc.content = "Modified"  # type: ignore[misc]


class TestDocumentParentRelationships:
    """Tests for parent-child document relationships."""

    def test_with_parent_creates_new_instance(self):
        """with_parent should return new Document instance."""
        original = Document(content="Test", type=DocumentType.ENRICHMENT_URL)
        with_parent = original.with_parent("parent-id")

        assert with_parent is not original
        assert with_parent.parent_id == "parent-id"
        assert original.parent_id is None

    def test_with_parent_preserves_content(self):
        """with_parent should preserve content and other fields."""
        original = Document(
            content="Enrichment content",
            type=DocumentType.ENRICHMENT_URL,
            metadata={"url": "https://example.com"},
            source_window="2025-01-10",
        )
        with_parent = original.with_parent("parent-id")

        assert with_parent.content == original.content
        assert with_parent.type == original.type
        assert with_parent.metadata == original.metadata
        assert with_parent.source_window == original.source_window

    def test_with_parent_copies_metadata(self):
        """with_parent should copy metadata (not share reference)."""
        original = Document(
            content="Test",
            type=DocumentType.ENRICHMENT_URL,
            metadata={"key": "value"},
        )
        with_parent = original.with_parent("parent-id")

        # Modify original's metadata should not affect copy
        original.metadata["key"] = "modified"  # type: ignore[index]

        assert with_parent.metadata == {"key": "value"}


class TestDocumentMetadataUpdates:
    """Tests for document metadata updates."""

    def test_with_metadata_creates_new_instance(self):
        """with_metadata should return new Document instance."""
        original = Document(
            content="Test",
            type=DocumentType.POST,
            metadata={"title": "Original"},
        )
        updated = original.with_metadata(title="Updated")

        assert updated is not original
        assert updated.metadata["title"] == "Updated"
        assert original.metadata["title"] == "Original"

    def test_with_metadata_updates_fields(self):
        """with_metadata should update specified fields."""
        doc = Document(
            content="Test",
            type=DocumentType.POST,
            metadata={"title": "Original", "author": "Alice"},
        )
        updated = doc.with_metadata(title="Updated", date="2025-01-10")

        assert updated.metadata == {
            "title": "Updated",
            "author": "Alice",
            "date": "2025-01-10",
        }

    def test_with_metadata_preserves_content(self):
        """with_metadata should preserve content and other fields."""
        original = Document(
            content="Content",
            type=DocumentType.POST,
            parent_id="parent-id",
            source_window="2025-01-10",
        )
        updated = original.with_metadata(title="Title")

        assert updated.content == original.content
        assert updated.type == original.type
        assert updated.parent_id == original.parent_id
        assert updated.source_window == original.source_window


class TestDocumentCollection:
    """Tests for DocumentCollection."""

    def test_collection_creation(self):
        """Can create document collection."""
        docs = [
            Document(content="Post 1", type=DocumentType.POST),
            Document(content="Post 2", type=DocumentType.POST),
        ]
        collection = DocumentCollection(documents=docs, window_label="2025-01-10")

        assert len(collection) == 2
        assert collection.window_label == "2025-01-10"

    def test_by_type_filters_correctly(self):
        """by_type should filter documents by type."""
        docs = [
            Document(content="Post 1", type=DocumentType.POST),
            Document(content="Profile", type=DocumentType.PROFILE),
            Document(content="Post 2", type=DocumentType.POST),
            Document(content="Journal", type=DocumentType.JOURNAL),
        ]
        collection = DocumentCollection(documents=docs)

        posts = collection.by_type(DocumentType.POST)
        assert len(posts) == 2
        assert all(doc.type == DocumentType.POST for doc in posts)

        profiles = collection.by_type(DocumentType.PROFILE)
        assert len(profiles) == 1
        assert profiles[0].content == "Profile"

    def test_find_children_returns_enrichments(self):
        """find_children should return all documents with matching parent."""
        parent_id = "media-doc-id"
        docs = [
            Document(content="Post", type=DocumentType.POST),
            Document(
                content="Enrichment 1",
                type=DocumentType.ENRICHMENT_URL,
                parent_id=parent_id,
            ),
            Document(
                content="Enrichment 2",
                type=DocumentType.ENRICHMENT_URL,
                parent_id=parent_id,
            ),
            Document(
                content="Other enrichment",
                type=DocumentType.ENRICHMENT_URL,
                parent_id="other-parent",
            ),
        ]
        collection = DocumentCollection(documents=docs)

        children = collection.find_children(parent_id)
        assert len(children) == 2
        assert all(doc.parent_id == parent_id for doc in children)

    def test_find_by_id_returns_document(self):
        """find_by_id should return document with matching ID."""
        doc1 = Document(content="Content 1", type=DocumentType.POST)
        doc2 = Document(content="Content 2", type=DocumentType.POST)
        collection = DocumentCollection(documents=[doc1, doc2])

        found = collection.find_by_id(doc1.document_id)
        assert found is doc1

        found = collection.find_by_id(doc2.document_id)
        assert found is doc2

    def test_find_by_id_returns_none_if_not_found(self):
        """find_by_id should return None if document not found."""
        collection = DocumentCollection(documents=[])

        found = collection.find_by_id("nonexistent-id")
        assert found is None

    def test_collection_iteration(self):
        """Can iterate over documents in collection."""
        docs = [
            Document(content="Doc 1", type=DocumentType.POST),
            Document(content="Doc 2", type=DocumentType.POST),
        ]
        collection = DocumentCollection(documents=docs)

        iterated = list(collection)
        assert iterated == docs

    def test_collection_len(self):
        """len() should return number of documents."""
        docs = [Document(content=f"Doc {i}", type=DocumentType.POST) for i in range(5)]
        collection = DocumentCollection(documents=docs)

        assert len(collection) == 5


class TestDocumentTypes:
    """Tests for DocumentType enumeration."""

    def test_all_document_types_exist(self):
        """All expected document types should be defined."""
        expected_types = {
            "POST",
            "PROFILE",
            "JOURNAL",
            "ENRICHMENT_URL",
            "ENRICHMENT_MEDIA",
            "MEDIA",
            "ANNOTATION",
        }

        actual_types = {dt.name for dt in DocumentType}
        assert actual_types == expected_types

    def test_document_type_values(self):
        """Document type values should match names (lowercase)."""
        for doc_type in DocumentType:
            assert doc_type.value == doc_type.name.lower()
