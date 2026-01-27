"""Tests for profile system routing.

Test-Driven Development: These tests define the expected behavior
before implementation is complete.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import Document, DocumentType
from egregora.output_sinks.exceptions import ProfileMetadataError
from egregora.output_sinks.mkdocs.adapter import MkDocsAdapter


@pytest.fixture
def adapter():
    """Create adapter instance for testing."""
    mock_ctx = Mock()
    mock_ctx.base_url = "http://example.com"
    mock_ctx.output_dir = Path("/tmp/test-output")
    mock_ctx.site_root = Path("/tmp/test-output")

    adapter = MkDocsAdapter()
    adapter._ctx = mock_ctx
    adapter.posts_dir = mock_ctx.output_dir / "docs" / "posts"
    adapter.profiles_dir = mock_ctx.output_dir / "docs" / "posts" / "profiles"
    adapter.docs_dir = mock_ctx.output_dir / "docs"

    return adapter


class TestPostRouting:
    """Test that regular posts go to top-level posts/."""

    def test_post_routes_to_top_level(self, adapter):
        """Regular POST goes to posts/{slug}.md (not author folder)."""
        doc = Document(
            content="# Test Post",
            type=DocumentType.POST,
            metadata={
                "title": "Test Post",
                "slug": "test-post",
                "authors": [{"uuid": "john-uuid", "name": "John"}],
            },
        )

        # Simulate URL from slug
        url = f"/posts/{doc.metadata['slug']}"
        path = adapter._url_to_path(url, doc)

        # Should be at top level, not in authors/
        assert "authors" not in str(path)
        assert path == adapter.posts_dir / "test-post.md"

    def test_post_with_multiple_authors_still_top_level(self, adapter):
        """Even with multiple authors, POST goes to top level."""
        doc = Document(
            content="# Collaborative Post",
            type=DocumentType.POST,
            metadata={
                "slug": "collaborative-post",
                "authors": [{"uuid": "john-uuid", "name": "John"}, {"uuid": "alice-uuid", "name": "Alice"}],
            },
        )

        url = f"/posts/{doc.metadata['slug']}"
        path = adapter._url_to_path(url, doc)
        assert "authors" not in str(path)
        assert path.name == "collaborative-post.md"


class TestProfileRouting:
    """Test that PROFILE posts go to author folders."""

    def test_profile_routes_to_author_folder(self, adapter):
        """PROFILE post goes to posts/authors/{uuid}/{slug}.md."""
        doc = Document(
            content="# John's Interests",
            type=DocumentType.PROFILE,
            metadata={
                "title": "John Doe: Interests",
                "slug": "john-interests",
                "authors": [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}],
                "subject": "john-uuid-12345678",
                "profile_aspect": "interests",
            },
        )

        url = f"/profiles/{doc.metadata['slug']}"
        path = adapter._url_to_path(url, doc)

        # Should be in author's folder (now located under profiles/, not posts/authors/)
        assert "profiles" in str(path)
        assert "john-uuid-12345678" in str(path)
        assert path.name == "john-interests.md"

    def test_profile_without_subject_raises_error(self, adapter):
        """PROFILE without subject metadata must raise a ProfileMetadataError."""
        doc = Document(
            content="# Profile",
            type=DocumentType.PROFILE,
            metadata={"slug": "orphan-profile", "authors": [{"uuid": EGREGORA_UUID}]},
        )
        url = f"/profiles/{doc.metadata['slug']}"
        with pytest.raises(ProfileMetadataError, match="missing required metadata field: 'subject'"):
            adapter._url_to_path(url, doc)

    def test_profile_author_is_egregora(self, adapter):
        """PROFILE posts should be authored by Egregora."""
        doc = Document(
            content="Analysis of John's contributions",
            type=DocumentType.PROFILE,
            metadata={
                "slug": "john-contributions",
                "authors": [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}],
                "subject": "john-uuid",
            },
        )

        # Verify Egregora is the author
        assert doc.metadata["authors"][0]["uuid"] == EGREGORA_UUID
        assert doc.metadata["authors"][0]["name"] == EGREGORA_NAME


class TestAnnouncementRouting:
    """Test that ANNOUNCEMENT posts go to announcements/."""

    def test_announcement_with_actor_routes_to_profile_folder(self, adapter):
        """ANNOUNCEMENT with an actor routes to the actor's profile folder."""
        actor_uuid = "john-uuid"
        doc = Document(
            content="# Avatar Updated",
            type=DocumentType.ANNOUNCEMENT,
            metadata={
                "title": "John Updated Avatar",
                "slug": "john-avatar-update",
                "authors": [{"uuid": EGREGORA_UUID}],
                "event_type": "avatar_update",
                "actor": actor_uuid,
            },
        )

        url = f"/announcements/{doc.metadata['slug']}"
        path = adapter._url_to_path(url, doc)

        # Should be in the actor's profile directory
        assert "announcements" not in str(path)
        assert str(adapter.profiles_dir / actor_uuid) in str(path)
        assert path == adapter.profiles_dir / actor_uuid / "john-avatar-update.md"

    def test_announcement_without_actor_routes_to_announcements_folder(self, adapter):
        """ANNOUNCEMENT without an actor falls back to the announcements folder."""
        doc = Document(
            content="# System Update",
            type=DocumentType.ANNOUNCEMENT,
            metadata={
                "title": "System Update",
                "slug": "system-update-v2",
                "authors": [{"uuid": EGREGORA_UUID}],
                "event_type": "system_update",
            },
        )
        url = f"/announcements/{doc.metadata['slug']}"
        path = adapter._url_to_path(url, doc)

        announcements_dir = adapter.posts_dir / "announcements"
        # Should be in the general announcements folder
        assert "profiles" not in str(path)
        assert "announcements" in str(path)
        assert path == announcements_dir / "system-update-v2.md"

    def test_announcement_author_is_egregora(self, adapter):
        """ANNOUNCEMENT posts authored by Egregora (system)."""
        doc = Document(
            content="System event",
            type=DocumentType.ANNOUNCEMENT,
            metadata={
                "slug": "bio-update",
                "authors": [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}],
                "event_type": "bio_update",
            },
        )

        assert doc.metadata["authors"][0]["uuid"] == EGREGORA_UUID


class TestRoutingIntegration:
    """Integration tests for complete routing behavior."""

    def test_different_types_separate_folders(self, adapter):
        """Verify all three types route to different locations."""
        post = Document(
            content="Regular post",
            type=DocumentType.POST,
            metadata={"slug": "regular", "authors": [{"uuid": "john-uuid"}]},
        )

        profile = Document(
            content="Profile",
            type=DocumentType.PROFILE,
            metadata={"slug": "john-profile", "authors": [{"uuid": EGREGORA_UUID}], "subject": "john-uuid"},
        )

        announcement = Document(
            content="Announcement",
            type=DocumentType.ANNOUNCEMENT,
            metadata={"slug": "update", "authors": [{"uuid": EGREGORA_UUID}]},
        )

        announcement_dir = adapter.posts_dir / "announcements"

        post_path = adapter._url_to_path("/posts/regular", post)
        profile_path = adapter._url_to_path("/profiles/john-profile", profile)
        announcement_path = adapter._url_to_path("/announcements/update", announcement)

        # All three should be in different locations
        assert str(post_path) != str(profile_path)
        assert str(post_path) != str(announcement_path)
        assert str(profile_path) != str(announcement_path)

        # Verify structure
        assert post_path == adapter.posts_dir / "regular.md"
        assert "profiles" in str(profile_path)
        assert announcement_path == announcement_dir / "update.md"

    def test_metadata_requirements(self, adapter):
        """Test that metadata is correctly structured."""
        # PROFILE requires 'subject'
        profile = Document(
            content="Profile",
            type=DocumentType.PROFILE,
            metadata={
                "slug": "test",
                "authors": [{"uuid": EGREGORA_UUID}],
                "subject": "john-uuid",  # Required!
                "profile_aspect": "interests",
            },
        )

        assert "subject" in profile.metadata
        assert profile.metadata["authors"][0]["uuid"] == EGREGORA_UUID

        # ANNOUNCEMENT requires 'event_type' and 'actor'
        announcement = Document(
            content="Update",
            type=DocumentType.ANNOUNCEMENT,
            metadata={
                "slug": "test",
                "authors": [{"uuid": EGREGORA_UUID}],
                "event_type": "avatar_update",  # Required!
                "actor": "john-uuid",  # Required!
            },
        )

        assert "event_type" in announcement.metadata
        assert "actor" in announcement.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
