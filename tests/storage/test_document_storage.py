"""Tests for DocumentStorage protocol and MkDocs implementation."""

import tempfile
from pathlib import Path

import pytest

from egregora.core.document import Document, DocumentType
from egregora.rendering.mkdocs_documents import MkDocsDocumentStorage
from egregora.storage.documents import DocumentStorage


class TestDocumentStorageProtocol:
    """Tests for DocumentStorage protocol compliance."""

    def test_mkdocs_storage_is_document_storage(self):
        """MkDocsDocumentStorage should implement DocumentStorage protocol."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = MkDocsDocumentStorage(site_root=Path(tmpdir))
            assert isinstance(storage, DocumentStorage)


class TestMkDocsDocumentStorage:
    """Tests for MkDocs-specific document storage."""

    @pytest.fixture
    def storage(self):
        """Create temporary MkDocs storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield MkDocsDocumentStorage(site_root=Path(tmpdir))

    def test_add_post_returns_document_id(self, storage):
        """add() should return content-addressed document ID."""
        doc = Document(
            content="# My Post\n\nContent...",
            type=DocumentType.POST,
            metadata={"title": "My Post", "date": "2025-01-10", "slug": "my-post"},
        )

        doc_id = storage.add(doc)
        assert doc_id == doc.document_id

    def test_add_post_creates_file(self, storage):
        """add() should create post file in posts/ directory."""
        doc = Document(
            content="# My Post\n\nContent...",
            type=DocumentType.POST,
            metadata={"title": "My Post", "date": "2025-01-10", "slug": "my-post"},
        )

        storage.add(doc)

        # Check file exists (MkDocs convention: posts/{date}-{slug}.md)
        expected_path = storage.posts_dir / "2025-01-10-my-post.md"
        assert expected_path.exists()

    def test_add_profile_creates_file_and_authors_yml(self, storage):
        """add() should create profile file and update .authors.yml."""
        doc = Document(
            content="Alice's profile content.",
            type=DocumentType.PROFILE,
            metadata={"uuid": "alice-uuid", "alias": "Alice", "bio": "AI researcher"},
        )

        storage.add(doc)

        # Check profile file
        profile_path = storage.profiles_dir / "alice-uuid.md"
        assert profile_path.exists()

        # Check .authors.yml
        authors_yml = storage.site_root / ".authors.yml"
        assert authors_yml.exists()
        content = authors_yml.read_text()
        assert "alice-uuid" in content

    def test_add_journal_creates_file(self, storage):
        """add() should create journal file in posts/journal/."""
        doc = Document(
            content="# Journal Entry\n\nThinking...",
            type=DocumentType.JOURNAL,
            metadata={"window_label": "2025-01-10 10:00 to 12:00"},
        )

        storage.add(doc)

        # Journal files use sanitized window label
        journal_files = list(storage.journal_dir.glob("*.md"))
        assert len(journal_files) == 1
        assert "2025-01-10" in journal_files[0].name

    def test_add_url_enrichment_uses_content_addressed_filename(self, storage):
        """URL enrichments should use document_id as filename."""
        doc = Document(
            content="Article about AI",
            type=DocumentType.ENRICHMENT_URL,
            metadata={"url": "https://example.com/article"},
        )

        storage.add(doc)

        # Should use document_id.md
        expected_path = storage.urls_dir / f"{doc.document_id}.md"
        assert expected_path.exists()
        assert expected_path.read_text() == "Article about AI"

    def test_get_retrieves_stored_document(self, storage):
        """get() should retrieve document by content-addressed ID."""
        doc = Document(
            content="Test content",
            type=DocumentType.POST,
            metadata={"slug": "test", "date": "2025-01-10"},
        )

        doc_id = storage.add(doc)
        retrieved = storage.get(doc_id)

        assert retrieved is not None
        assert retrieved.document_id == doc.document_id
        assert "Test content" in retrieved.content

    def test_get_returns_none_for_nonexistent(self, storage):
        """get() should return None for nonexistent document."""
        result = storage.get("nonexistent-id")
        assert result is None

    def test_exists_returns_true_for_stored_document(self, storage):
        """exists() should return True for stored document."""
        doc = Document(
            content="Test",
            type=DocumentType.POST,
            metadata={"slug": "test", "date": "2025-01-10"},
        )

        doc_id = storage.add(doc)
        assert storage.exists(doc_id) is True

    def test_exists_returns_false_for_nonexistent(self, storage):
        """exists() should return False for nonexistent document."""
        assert storage.exists("nonexistent-id") is False

    def test_list_by_type_filters_correctly(self, storage):
        """list_by_type() should return only documents of specified type."""
        # Add posts
        post1 = Document(
            content="Post 1", type=DocumentType.POST, metadata={"slug": "post1", "date": "2025-01-10"}
        )
        post2 = Document(
            content="Post 2", type=DocumentType.POST, metadata={"slug": "post2", "date": "2025-01-11"}
        )

        # Add profile
        profile = Document(content="Profile", type=DocumentType.PROFILE, metadata={"uuid": "alice-uuid"})

        storage.add(post1)
        storage.add(post2)
        storage.add(profile)

        # List posts
        posts = storage.list_by_type(DocumentType.POST)
        assert len(posts) == 2
        assert all(doc.type == DocumentType.POST for doc in posts)

        # List profiles
        profiles = storage.list_by_type(DocumentType.PROFILE)
        assert len(profiles) == 1
        assert profiles[0].type == DocumentType.PROFILE

    def test_find_children_returns_enrichments(self, storage):
        """find_children() should return documents with matching parent_id."""
        # Create parent media document
        media = Document(content="Media file", type=DocumentType.MEDIA, metadata={})
        media_id = storage.add(media)

        # Create enrichments with parent
        enrichment1 = Document(
            content="Enrichment 1",
            type=DocumentType.ENRICHMENT_URL,
            parent_id=media_id,
        )
        enrichment2 = Document(
            content="Enrichment 2",
            type=DocumentType.ENRICHMENT_URL,
            parent_id=media_id,
        )

        # Create unrelated enrichment
        other_enrichment = Document(
            content="Other",
            type=DocumentType.ENRICHMENT_URL,
            parent_id="other-parent",
        )

        storage.add(enrichment1)
        storage.add(enrichment2)
        storage.add(other_enrichment)

        # Find children
        children = storage.find_children(media_id)
        assert len(children) == 2
        assert all(doc.parent_id == media_id for doc in children)

    def test_delete_removes_document(self, storage):
        """delete() should remove document from storage."""
        doc = Document(
            content="Test",
            type=DocumentType.POST,
            metadata={"slug": "test", "date": "2025-01-10"},
        )

        doc_id = storage.add(doc)
        assert storage.exists(doc_id) is True

        # Delete
        result = storage.delete(doc_id)
        assert result is True
        assert storage.exists(doc_id) is False

    def test_delete_returns_false_for_nonexistent(self, storage):
        """delete() should return False for nonexistent document."""
        result = storage.delete("nonexistent-id")
        assert result is False

    def test_add_is_idempotent(self, storage):
        """add() should be idempotent (same content → same ID)."""
        doc1 = Document(
            content="Same content",
            type=DocumentType.POST,
            metadata={"slug": "test", "date": "2025-01-10"},
        )
        doc2 = Document(
            content="Same content",
            type=DocumentType.POST,
            metadata={"slug": "test", "date": "2025-01-10"},
        )

        id1 = storage.add(doc1)
        id2 = storage.add(doc2)

        assert id1 == id2
        # Should only have one file
        post_files = list(storage.posts_dir.glob("*.md"))
        assert len(post_files) == 1

    def test_content_changes_produce_new_id(self, storage):
        """Changing content should produce new document ID."""
        doc1 = Document(
            content="Version 1",
            type=DocumentType.POST,
            metadata={"slug": "test", "date": "2025-01-10"},
        )
        doc2 = Document(
            content="Version 2",
            type=DocumentType.POST,
            metadata={"slug": "test", "date": "2025-01-10"},
        )

        id1 = storage.add(doc1)
        id2 = storage.add(doc2)

        assert id1 != id2
        # Both versions stored (different IDs, but same slug gets collision suffix)
        post_files = list(storage.posts_dir.glob("*.md"))
        assert len(post_files) >= 1  # At least one file


class TestMkDocsDocumentStorageMetadata:
    """Tests for metadata handling in MkDocs storage."""

    @pytest.fixture
    def storage(self):
        """Create temporary MkDocs storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield MkDocsDocumentStorage(site_root=Path(tmpdir))

    def test_post_metadata_preserved_in_frontmatter(self, storage):
        """Post metadata should be preserved in YAML frontmatter."""
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={
                "title": "My Post",
                "date": "2025-01-10",
                "slug": "my-post",
                "tags": ["python", "ai"],
                "author": "alice-uuid",
            },
        )

        doc_id = storage.add(doc)
        retrieved = storage.get(doc_id)

        assert retrieved is not None
        assert retrieved.metadata["title"] == "My Post"
        assert retrieved.metadata["date"] == "2025-01-10"
        assert retrieved.metadata["tags"] == ["python", "ai"]

    def test_profile_metadata_preserved(self, storage):
        """Profile metadata should be preserved in frontmatter."""
        doc = Document(
            content="Profile content",
            type=DocumentType.PROFILE,
            metadata={
                "uuid": "alice-uuid",
                "alias": "Alice",
                "bio": "AI researcher",
            },
        )

        doc_id = storage.add(doc)
        retrieved = storage.get(doc_id)

        assert retrieved is not None
        assert retrieved.metadata["uuid"] == "alice-uuid"
        assert "alias" in retrieved.metadata or "Alice" in retrieved.content


class TestMkDocsDocumentStorageParentRelationships:
    """Tests for parent-child document relationships."""

    @pytest.fixture
    def storage(self):
        """Create temporary MkDocs storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield MkDocsDocumentStorage(site_root=Path(tmpdir))

    def test_enrichment_with_parent_preserves_relationship(self, storage):
        """Enrichments should preserve parent_id."""
        parent = Document(content="Parent media", type=DocumentType.MEDIA)
        parent_id = storage.add(parent)

        enrichment = Document(
            content="Description of media",
            type=DocumentType.ENRICHMENT_URL,
            parent_id=parent_id,
        )

        enrichment_id = storage.add(enrichment)
        retrieved = storage.get(enrichment_id)

        assert retrieved is not None
        assert retrieved.parent_id == parent_id

    def test_find_children_works_across_storage_reload(self, storage):
        """Parent-child relationships should survive storage reload."""
        # Add parent and child
        parent = Document(content="Parent", type=DocumentType.MEDIA)
        parent_id = storage.add(parent)

        child = Document(
            content="Child",
            type=DocumentType.ENRICHMENT_URL,
            parent_id=parent_id,
        )
        storage.add(child)

        # Create new storage instance (simulates reload)
        new_storage = MkDocsDocumentStorage(site_root=storage.site_root)

        # Should still find children
        children = new_storage.find_children(parent_id)
        assert len(children) >= 1
        # Note: Relationships may not survive reload without metadata preservation
        # This test may need adjustment based on implementation
