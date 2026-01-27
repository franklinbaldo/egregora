"""End-to-end tests for profile document routing.

Verifies that profile Documents with proper metadata route to the correct
directory structure: /docs/posts/profiles/{author_uuid}/{slug}.md
"""

import pytest

from egregora.constants import EGREGORA_NAME, EGREGORA_UUID
from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.output_sinks.conventions import StandardUrlConvention


class TestProfileRoutingEndToEnd:
    """End-to-end tests for complete profile routing flow."""

    @pytest.fixture
    def convention(self):
        """Create URL convention instance."""
        return StandardUrlConvention()

    @pytest.fixture
    def ctx(self):
        """Create URL context for testing."""
        return UrlContext(base_url="https://example.com", site_prefix="blog")

    def test_profile_with_subject_routes_to_author_directory(self, convention, ctx):
        """Profile with subject metadata should route to author-specific URL."""
        author_uuid = "550e8400-e29b-41d4-a716-446655440000"
        doc = Document(
            content="# Author Analysis",
            type=DocumentType.PROFILE,
            metadata={
                "subject": author_uuid,
                "slug": "contributions-analysis",
                "authors": [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}],
            },
        )

        url = convention.canonical_url(doc, ctx)

        # Should route to /blog/profiles/{uuid}/{slug}/
        assert f"/profiles/{author_uuid}/contributions-analysis/" in url
        assert url.startswith("https://example.com/blog/")

    def test_profile_without_subject_falls_back_to_posts(self, convention, ctx):
        """Profile without subject should fall back to posts directory."""
        doc = Document(
            content="# Orphan Profile",
            type=DocumentType.PROFILE,
            metadata={
                "slug": "orphan-profile",
                "authors": [{"uuid": EGREGORA_UUID, "name": EGREGORA_NAME}],
            },
        )

        url = convention.canonical_url(doc, ctx)

        # Should fall back to /blog/posts/{slug}/
        assert "/posts/orphan-profile/" in url
        assert "/profiles/" not in url

    def test_multiple_profiles_same_author_different_slugs(self, convention, ctx):
        """Multiple profiles for same author should all route to their directory."""
        author_uuid = "test-author-123"

        profiles = [
            Document(
                content=f"# Profile {i}",
                type=DocumentType.PROFILE,
                metadata={
                    "subject": author_uuid,
                    "slug": f"profile-{i}",
                    "authors": [{"uuid": EGREGORA_UUID}],
                },
            )
            for i in range(3)
        ]

        urls = [convention.canonical_url(doc, ctx) for doc in profiles]

        # All should route to same author directory but different files
        for i, url in enumerate(urls):
            assert f"/profiles/{author_uuid}/profile-{i}/" in url

    def test_profile_routing_with_date_metadata(self, convention, ctx):
        """Profile with date should still route by subject, not date."""
        author_uuid = "test-author-456"
        doc = Document(
            content="# Monthly Analysis",
            type=DocumentType.PROFILE,
            metadata={
                "subject": author_uuid,
                "slug": "monthly-analysis",
                "date": "2025-03-15",
                "authors": [{"uuid": EGREGORA_UUID}],
            },
        )

        url = convention.canonical_url(doc, ctx)

        # Should route to /profiles/{uuid}/{slug}/, NOT /profiles/2025-03-15-...
        assert f"/profiles/{author_uuid}/monthly-analysis/" in url
        assert "2025-03-15" not in url  # Date should not be in URL for profiles

    def test_profile_with_special_characters_in_slug(self, convention, ctx):
        """Profile slug should be properly slugified."""
        author_uuid = "test-author-789"
        doc = Document(
            content="# Special Analysis",
            type=DocumentType.PROFILE,
            metadata={
                "subject": author_uuid,
                "slug": "John's Contributions & Interests!",
                "authors": [{"uuid": EGREGORA_UUID}],
            },
        )

        url = convention.canonical_url(doc, ctx)

        # Slug should be sanitized
        assert f"/profiles/{author_uuid}/" in url
        # Special characters should be handled
        assert "!" not in url
        assert "&" not in url

    def test_profile_uses_subject_over_uuid_metadata(self, convention, ctx):
        """Profile should prefer 'subject' over 'uuid' for routing."""
        subject_uuid = "subject-123"
        doc = Document(
            content="# Profile",
            type=DocumentType.PROFILE,
            metadata={
                "subject": subject_uuid,
                "uuid": "different-uuid-456",  # Should be ignored
                "slug": "test-profile",
                "authors": [{"uuid": EGREGORA_UUID}],
            },
        )

        url = convention.canonical_url(doc, ctx)

        # Should use subject, not uuid
        assert f"/profiles/{subject_uuid}/" in url
        assert "different-uuid-456" not in url

    def test_profile_fallback_to_uuid_if_no_subject(self, convention, ctx):
        """If subject is missing, should try uuid metadata."""
        uuid_value = "fallback-uuid-789"
        doc = Document(
            content="# Profile",
            type=DocumentType.PROFILE,
            metadata={
                "uuid": uuid_value,
                "slug": "test-profile",
                "authors": [{"uuid": EGREGORA_UUID}],
            },
        )

        url = convention.canonical_url(doc, ctx)

        # Should fall back to uuid metadata
        assert f"/profiles/{uuid_value}/" in url


class TestProfileRoutingConsistency:
    """Tests to ensure consistent routing across different scenarios."""

    @pytest.fixture
    def convention(self):
        return StandardUrlConvention()

    @pytest.fixture
    def ctx(self):
        return UrlContext(base_url="", site_prefix="")

    def test_same_subject_produces_consistent_urls(self, convention, ctx):
        """Same subject should always produce URLs in same directory."""
        author_uuid = "consistent-author"

        urls = []
        for i in range(5):
            doc = Document(
                content=f"# Profile {i}",
                type=DocumentType.PROFILE,
                metadata={
                    "subject": author_uuid,
                    "slug": f"profile-{i}",
                    "authors": [{"uuid": EGREGORA_UUID}],
                },
            )
            urls.append(convention.canonical_url(doc, ctx))

        # All URLs should contain same author directory
        for url in urls:
            assert f"/profiles/{author_uuid}/" in url

    def test_different_subjects_produce_different_directories(self, convention, ctx):
        """Different subjects should produce URLs in different directories."""
        authors = [f"author-{i}" for i in range(3)]

        urls = [
            convention.canonical_url(
                Document(
                    content=f"# Profile for {author}",
                    type=DocumentType.PROFILE,
                    metadata={
                        "subject": author,
                        "slug": "profile",
                        "authors": [{"uuid": EGREGORA_UUID}],
                    },
                ),
                ctx,
            )
            for author in authors
        ]

        # Each should have unique directory
        for i, author in enumerate(authors):
            assert f"/profiles/{author}/" in urls[i]

        # No URL should contain another author's directory
        for i, url in enumerate(urls):
            for j, author in enumerate(authors):
                if i != j:
                    assert f"/profiles/{author}/" not in url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
