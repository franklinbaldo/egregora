"""Test unified directory structure for MkDocs adapter.

Tests that all document types (posts, profiles, journals, enrichment) are correctly
stored in a single posts/ directory with proper category-based organization.
"""

import pytest
import yaml

from egregora.data_primitives.document import Document, DocumentType
from egregora.output_adapters.mkdocs import MkDocsAdapter


@pytest.fixture
def adapter(tmp_path):
    """Fixture to create and initialize an MkDocsAdapter."""
    adapter = MkDocsAdapter()
    adapter.initialize(tmp_path)
    return adapter


class TestUnifiedDirectoryStructure:
    """Test that all documents go to posts_dir with proper categorization."""

    def test_posts_profiles_and_journals_share_same_directory(self, adapter):
        """Verify that posts_dir, profiles_dir, and journal_dir point to the same location."""
        assert adapter.posts_dir == adapter.profiles_dir
        assert adapter.posts_dir == adapter.journal_dir

    def test_post_persists_to_posts_dir_without_category(self, adapter):
        """Posts should go to posts_dir without forcing a category."""
        post = Document(
            content="# Test Post",
            type=DocumentType.POST,
            metadata={
                "title": "Test Post",
                "date": "2024-01-01",
                "slug": "test-post",
                "tags": ["test"],
            },
        )
        adapter.persist(post)

        # Check file is in posts_dir
        post_path = adapter.posts_dir / "2024-01-01-test-post.md"
        assert post_path.exists()

        # Parse frontmatter
        content = post_path.read_text(encoding="utf-8")
        _, frontmatter_str, _ = content.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter_str)

        # Posts without explicit categories should not have category forced
        # (Material blog shows them in main feed)
        assert "categories" not in metadata or len(metadata.get("categories", [])) == 0

    def test_profile_persists_to_posts_dir_with_authors_category(self, adapter):
        """Profiles should go to posts_dir with 'Authors' category."""
        profile = Document(
            content="# User Bio",
            type=DocumentType.PROFILE,
            metadata={"uuid": "user-123", "name": "Test User"},
        )
        adapter.persist(profile)

        # Check file is in posts_dir (same as profiles_dir)
        profile_path = adapter.posts_dir / "user-123.md"
        assert profile_path.exists()

        # Parse frontmatter
        content = profile_path.read_text(encoding="utf-8")
        _, frontmatter_str, _ = content.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter_str)

        # Should have Authors category
        assert "categories" in metadata
        assert "Authors" in metadata["categories"]

    def test_journal_persists_to_posts_dir_with_journal_category(self, adapter):
        """Journal entries should go to posts_dir with 'Journal' category."""
        journal = Document(
            content="# Journal Entry",
            type=DocumentType.JOURNAL,
            metadata={"slug": "journal-entry", "date": "2024-01-01"},
        )
        adapter.persist(journal)

        # Check file is in posts_dir (same as journal_dir)
        journal_path = adapter.posts_dir / "journal-entry.md"
        assert journal_path.exists()

        # Parse frontmatter
        content = journal_path.read_text(encoding="utf-8")
        _, frontmatter_str, _ = content.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter_str)

        # Should have Journal category
        assert "categories" in metadata
        assert "Journal" in metadata["categories"]

    def test_enrichment_url_persists_to_posts_dir_with_enrichment_category(self, adapter):
        """Enrichment URLs should go to posts_dir with 'Enrichment' category."""
        enrichment = Document(
            content="# Enriched Content",
            type=DocumentType.ENRICHMENT_URL,
            metadata={"slug": "enriched-url", "url": "https://example.com"},
        )
        adapter.persist(enrichment)

        # Check file is in posts_dir (note: enrichment URLs include hash suffix for uniqueness)
        matching_files = list(adapter.posts_dir.glob("enriched-url*.md"))
        assert len(matching_files) == 1, f"Expected 1 enriched-url file, found {len(matching_files)}"
        enrichment_path = matching_files[0]

        # Parse frontmatter
        content = enrichment_path.read_text(encoding="utf-8")
        _, frontmatter_str, _ = content.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter_str)

        # Should have Enrichment category
        assert "categories" in metadata
        assert "Enrichment" in metadata["categories"]


class TestCategoryValidation:
    """Test that category handling is robust against malformed data."""

    def test_profile_with_malformed_categories_still_gets_authors(self, adapter):
        """Profiles with malformed categories should still get 'Authors' category."""
        profile = Document(
            content="# User Bio",
            type=DocumentType.PROFILE,
            metadata={
                "uuid": "user-malformed",
                "name": "Test User",
                "categories": "not-a-list",  # Malformed: string instead of list
            },
        )
        adapter.persist(profile)

        profile_path = adapter.posts_dir / "user-malformed.md"
        content = profile_path.read_text(encoding="utf-8")
        _, frontmatter_str, _ = content.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter_str)

        # Should have converted to list and added Authors
        assert isinstance(metadata["categories"], list)
        assert "Authors" in metadata["categories"]

    def test_journal_preserves_existing_categories(self, adapter):
        """Journal entries should preserve existing categories while adding 'Journal'."""
        journal = Document(
            content="# Journal Entry",
            type=DocumentType.JOURNAL,
            metadata={
                "slug": "journal-multi-cat",
                "date": "2024-01-01",
                "categories": ["Personal", "Thoughts"],
            },
        )
        adapter.persist(journal)

        journal_path = adapter.posts_dir / "journal-multi-cat.md"
        content = journal_path.read_text(encoding="utf-8")
        _, frontmatter_str, _ = content.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter_str)

        # Should preserve existing and add Journal
        assert "Personal" in metadata["categories"]
        assert "Thoughts" in metadata["categories"]
        assert "Journal" in metadata["categories"]

    def test_profile_doesnt_duplicate_authors_category(self, adapter):
        """Profiles that already have 'Authors' category should not duplicate it."""
        profile = Document(
            content="# User Bio",
            type=DocumentType.PROFILE,
            metadata={
                "uuid": "user-no-dup",
                "name": "Test User",
                "categories": ["Authors", "Team"],
            },
        )
        adapter.persist(profile)

        profile_path = adapter.posts_dir / "user-no-dup.md"
        content = profile_path.read_text(encoding="utf-8")
        _, frontmatter_str, _ = content.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter_str)

        # Should only have one Authors entry
        assert metadata["categories"].count("Authors") == 1
        assert "Team" in metadata["categories"]


class TestListMethodConsistency:
    """Test that list() method correctly identifies document types in unified directory."""

    def test_list_distinguishes_document_types_by_category(self, adapter):
        """list() should identify document types by reading their category metadata."""
        # Create different document types
        post = Document(
            content="# Post",
            type=DocumentType.POST,
            metadata={
                "title": "Post",
                "date": "2024-01-01",
                "slug": "post-type-test",
                "tags": ["test"],
            },
        )
        profile = Document(
            content="# Profile",
            type=DocumentType.PROFILE,
            metadata={"uuid": "profile-type-test", "name": "Test User"},
        )
        journal = Document(
            content="# Journal",
            type=DocumentType.JOURNAL,
            metadata={"slug": "journal-type-test", "date": "2024-01-01"},
        )

        # Persist all
        adapter.persist(post)
        adapter.persist(profile)
        adapter.persist(journal)

        # List all documents
        all_docs = list(adapter.list())

        # Should have exactly 3 documents with correct types
        assert len(all_docs) == 3

        # Check types are correctly identified
        doc_types = {doc.doc_type for doc in all_docs}
        assert DocumentType.POST in doc_types
        assert DocumentType.PROFILE in doc_types
        assert DocumentType.JOURNAL in doc_types

    def test_list_does_not_duplicate_documents(self, adapter):
        """list() should not scan the same directory multiple times."""
        # Create a profile
        profile = Document(
            content="# Profile",
            type=DocumentType.PROFILE,
            metadata={"uuid": "no-dup-test", "name": "No Dup Test"},
        )
        adapter.persist(profile)

        # List all documents
        all_docs = list(adapter.list())

        # Should have exactly 1 document, not duplicated
        assert len(all_docs) == 1
        assert all_docs[0].doc_type == DocumentType.PROFILE

    def test_list_and_persist_are_consistent_for_enrichments(self, adapter):
        """Enrichment URLs should be found by list() where persist() writes them."""
        enrichment = Document(
            content="# Enrichment",
            type=DocumentType.ENRICHMENT_URL,
            metadata={"slug": "enrich-consistency", "url": "https://example.com"},
        )
        adapter.persist(enrichment)

        # List enrichments specifically
        enrichments = list(adapter.list(doc_type=DocumentType.ENRICHMENT_URL))

        # Should find the enrichment we just persisted
        assert len(enrichments) == 1
        assert enrichments[0].doc_type == DocumentType.ENRICHMENT_URL


class TestNamingCollisions:
    """Test handling of potential naming collisions in unified directory."""

    def test_profile_and_post_with_same_slug_dont_collide(self, adapter):
        """Profile 'alice' and post with slug 'alice' should have different filenames."""
        # Create profile
        profile = Document(
            content="# Alice Profile",
            type=DocumentType.PROFILE,
            metadata={"uuid": "alice", "name": "Alice"},
        )

        # Create post with same slug
        post = Document(
            content="# Alice Post",
            type=DocumentType.POST,
            metadata={
                "title": "Alice",
                "date": "2024-01-01",
                "slug": "alice",
                "tags": ["test"],
            },
        )

        # Persist both
        adapter.persist(profile)
        adapter.persist(post)

        # Both should exist with different filenames
        profile_path = adapter.posts_dir / "alice.md"
        post_path = adapter.posts_dir / "2024-01-01-alice.md"

        assert profile_path.exists()
        assert post_path.exists()

        # Verify they contain different content
        profile_content = profile_path.read_text()
        post_content = post_path.read_text()

        assert "Alice Profile" in profile_content
        assert "Alice Post" in post_content

    def test_journal_and_enrichment_with_same_slug_handled(self, adapter):
        """Journal and enrichment with same slug should coexist or be handled gracefully."""
        # Create journal entry
        journal = Document(
            content="# Same Slug Journal",
            type=DocumentType.JOURNAL,
            metadata={"slug": "same-slug", "date": "2024-01-01"},
        )

        # Create enrichment with same slug
        enrichment = Document(
            content="# Same Slug Enrichment",
            type=DocumentType.ENRICHMENT_URL,
            metadata={"slug": "same-slug", "url": "https://example.com"},
        )

        # Persist both
        adapter.persist(journal)
        adapter.persist(enrichment)

        # Check what happened - could be collision handling or last-write-wins
        # At minimum, should not crash
        expected_path = adapter.posts_dir / "same-slug.md"
        assert expected_path.exists()

        # Read content and check metadata to see which one won
        content = expected_path.read_text()
        _, frontmatter_str, _ = content.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter_str)

        # Should have either Journal or Enrichment category, not both conflicting
        categories = metadata.get("categories", [])
        assert "Journal" in categories or "Enrichment" in categories


class TestDocumentRetrieval:
    """Test that documents can be retrieved correctly from unified directory."""

    def test_get_profile_by_identifier(self, adapter):
        """get() should retrieve profiles correctly."""
        profile = Document(
            content="# Retrievable Profile",
            type=DocumentType.PROFILE,
            metadata={"uuid": "get-test", "name": "Get Test"},
        )
        adapter.persist(profile)

        # Retrieve by identifier
        retrieved = adapter.get(DocumentType.PROFILE, "get-test")

        assert retrieved is not None
        assert retrieved.type == DocumentType.PROFILE
        assert "Retrievable Profile" in retrieved.content

    def test_get_post_by_slug(self, adapter):
        """get() should retrieve posts correctly."""
        post = Document(
            content="# Retrievable Post",
            type=DocumentType.POST,
            metadata={
                "title": "Retrievable",
                "date": "2024-01-01",
                "slug": "retrievable",
                "tags": ["test"],
            },
        )
        adapter.persist(post)

        # Retrieve by slug
        retrieved = adapter.get(DocumentType.POST, "retrievable")

        assert retrieved is not None
        assert retrieved.type == DocumentType.POST
        assert "Retrievable Post" in retrieved.content


class TestDeadCodeRemoval:
    """Test that dead code has been properly removed or fixed."""

    def test_urls_dir_is_not_created_when_enrichments_go_to_posts(self, adapter):
        """If enrichment URLs go to posts_dir, urls_dir shouldn't be created/used."""
        # Create enrichment
        enrichment = Document(
            content="# Enrichment",
            type=DocumentType.ENRICHMENT_URL,
            metadata={"slug": "urls-dir-test", "url": "https://example.com"},
        )
        adapter.persist(enrichment)

        # Check enrichment is in posts_dir (note: enrichment URLs include hash suffix for uniqueness)
        matching_files = list(adapter.posts_dir.glob("urls-dir-test*.md"))
        assert len(matching_files) == 1, (
            f"Expected 1 urls-dir-test file in posts_dir, found {len(matching_files)}"
        )

        # urls_dir should not be created if it's supposed to be consolidated with posts_dir
        urls_dir = getattr(adapter, "urls_dir", None)
        if urls_dir and urls_dir.exists():
            urls_files = list(urls_dir.glob("*.md"))
            # Should be empty or only contain non-enrichment files
            assert len(urls_files) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
