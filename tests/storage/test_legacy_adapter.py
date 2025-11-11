"""Tests for LegacyStorageAdapter."""

import tempfile
from pathlib import Path

import pytest
from egregora.storage.legacy_adapter import LegacyStorageAdapter

from egregora.core.document import Document, DocumentType
from egregora.rendering.mkdocs import MkDocsJournalStorage, MkDocsPostStorage, MkDocsProfileStorage
from egregora.storage.documents import DocumentStorage


class TestLegacyStorageAdapter:
    """Tests for legacy storage adapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with temporary MkDocs storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            site_root = Path(tmpdir)
            post_storage = MkDocsPostStorage(site_root)
            profile_storage = MkDocsProfileStorage(site_root)
            journal_storage = MkDocsJournalStorage(site_root)

            adapter = LegacyStorageAdapter(
                post_storage=post_storage,
                profile_storage=profile_storage,
                journal_storage=journal_storage,
                site_root=site_root,
            )
            yield adapter

    def test_adapter_is_document_storage(self, adapter):
        """LegacyStorageAdapter should implement DocumentStorage protocol."""
        assert isinstance(adapter, DocumentStorage)

    def test_add_post_returns_document_id(self, adapter):
        """add() should return content-addressed document ID."""
        doc = Document(
            content="# My Post\n\nContent...",
            type=DocumentType.POST,
            metadata={"title": "My Post", "date": "2025-01-10", "slug": "my-post"},
        )

        doc_id = adapter.add(doc)
        assert doc_id == doc.document_id

    def test_add_post_creates_file_via_old_storage(self, adapter):
        """add() should delegate to old PostStorage.write()."""
        doc = Document(
            content="Test content",
            type=DocumentType.POST,
            metadata={"slug": "test-post", "date": "2025-01-10"},
        )

        adapter.add(doc)

        # Verify file was created by old storage
        posts_dir = adapter.site_root / "posts"
        post_files = list(posts_dir.glob("*.md"))
        assert len(post_files) >= 1
        # Filename should contain the slug
        assert any("test-post" in f.name for f in post_files)

    def test_add_profile_creates_file_via_old_storage(self, adapter):
        """add() should delegate to old ProfileStorage.write()."""
        doc = Document(
            content="Alice's profile",
            type=DocumentType.PROFILE,
            metadata={"uuid": "alice-uuid"},
        )

        adapter.add(doc)

        # Verify file was created by old storage
        profiles_dir = adapter.site_root / "profiles"
        profile_file = profiles_dir / "alice-uuid.md"
        assert profile_file.exists()

    def test_add_journal_creates_file_via_old_storage(self, adapter):
        """add() should delegate to old JournalStorage.write()."""
        doc = Document(
            content="Journal entry",
            type=DocumentType.JOURNAL,
            metadata={"window_label": "2025-01-10 10:00 to 12:00"},
        )

        adapter.add(doc)

        # Verify file was created by old storage
        journal_dir = adapter.site_root / "posts" / "journal"
        journal_files = list(journal_dir.glob("*.md"))
        assert len(journal_files) >= 1

    def test_add_unsupported_type_raises_error(self, adapter):
        """add() should raise ValueError for unsupported document types."""
        doc = Document(
            content="Enrichment",
            type=DocumentType.ENRICHMENT_URL,
            metadata={},
        )

        with pytest.raises(ValueError, match="Unsupported document type"):
            adapter.add(doc)

    def test_get_returns_none(self, adapter):
        """get() should return None (legacy storage doesn't support retrieval)."""
        result = adapter.get("some-document-id")
        assert result is None

    def test_exists_returns_false(self, adapter):
        """exists() should return False (legacy storage doesn't support lookups)."""
        result = adapter.exists("some-document-id")
        assert result is False

    def test_list_by_type_returns_empty(self, adapter):
        """list_by_type() should return empty list (legacy storage doesn't support listing)."""
        result = adapter.list_by_type(DocumentType.POST)
        assert result == []

    def test_find_children_returns_empty(self, adapter):
        """find_children() should return empty list (legacy storage doesn't support parent relationships)."""
        result = adapter.find_children("parent-id")
        assert result == []

    def test_delete_returns_false(self, adapter):
        """delete() should return False (legacy storage doesn't support deletion)."""
        result = adapter.delete("some-document-id")
        assert result is False

    def test_profile_without_uuid_raises_error(self, adapter):
        """Profile documents must have uuid in metadata."""
        doc = Document(
            content="Profile without UUID",
            type=DocumentType.PROFILE,
            metadata={},
        )

        with pytest.raises(ValueError, match="must have 'uuid' or 'author_uuid'"):
            adapter.add(doc)
