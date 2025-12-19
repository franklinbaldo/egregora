"""Tests for profile slug generation and append-only behavior.

Verifies that profile posts use meaningful slugs and support
append-only architecture.
"""

import pytest

from egregora.agents.profile.generator import _generate_meaningful_slug


class TestMeaningfulSlugGeneration:
    """Test meaningful slug generation for profile posts."""

    def test_slug_includes_date_aspect_and_author(self):
        """Slug should include date, aspect, and author identifier."""
        slug = _generate_meaningful_slug(
            title="John Doe: Technical Contributions", window_date="2025-03-15", author_uuid="550e8400-abcd-1234"
        )

        # Should include date
        assert slug.startswith("2025-03-15-")
        # Should include aspect (slugified "Technical Contributions")
        assert "technical-contributions" in slug
        # Should include author ID (first 8 chars)
        assert slug.endswith("-550e8400")

    def test_slug_with_title_without_colon(self):
        """Handle titles without author name prefix."""
        slug = _generate_meaningful_slug(
            title="Photography Interests and Gear", window_date="2025-04-01", author_uuid="alice123-456"
        )

        assert slug.startswith("2025-04-01-")
        assert "photography-interests" in slug
        assert slug.endswith("-alice123")

    def test_slug_uniqueness_across_different_aspects(self):
        """Different aspects should produce different slugs."""
        base_params = {"window_date": "2025-03-15", "author_uuid": "test-uuid-123"}

        slug1 = _generate_meaningful_slug(title="John: Technical Skills", **base_params)
        slug2 = _generate_meaningful_slug(title="John: Photography Interests", **base_params)
        slug3 = _generate_meaningful_slug(title="John: Community Engagement", **base_params)

        # All should be different
        assert slug1 != slug2 != slug3

        # All should have same date and author
        assert all(s.startswith("2025-03-15-") for s in [slug1, slug2, slug3])
        assert all(s.endswith("-test-uui") for s in [slug1, slug2, slug3])

    def test_slug_uniqueness_across_different_dates(self):
        """Same aspect on different dates should produce different slugs."""
        slug1 = _generate_meaningful_slug(
            title="Alice: Photography", window_date="2025-03-01", author_uuid="alice-123"
        )
        slug2 = _generate_meaningful_slug(
            title="Alice: Photography", window_date="2025-03-15", author_uuid="alice-123"
        )

        assert slug1 != slug2
        assert slug1.startswith("2025-03-01-")
        assert slug2.startswith("2025-03-15-")

    def test_slug_special_characters_handled(self):
        """Special characters in title should be properly slugified."""
        slug = _generate_meaningful_slug(
            title="John's Amazing Contributions & Ideas!", window_date="2025-03-15", author_uuid="john-uuid"
        )

        # Should not contain special characters
        assert "'" not in slug
        assert "&" not in slug
        assert "!" not in slug

        # Should contain slugified version
        assert "amazing-contributions" in slug
        assert "ideas" in slug

    def test_slug_consistency(self):
        """Same inputs should produce same slug (deterministic)."""
        params = {
            "title": "Test Profile: Key Insights",
            "window_date": "2025-03-15",
            "author_uuid": "test-123",
        }

        slug1 = _generate_meaningful_slug(**params)
        slug2 = _generate_meaningful_slug(**params)

        assert slug1 == slug2

    def test_slug_format_structure(self):
        """Verify the expected format: date-aspect-authorid."""
        slug = _generate_meaningful_slug(
            title="Bob: Machine Learning Insights", window_date="2025-05-20", author_uuid="bobsmith-uuid-789"
        )

        # Split and verify structure
        parts = slug.split("-")

        # Should start with date (YYYY-MM-DD = 3 parts)
        assert parts[0] == "2025"
        assert parts[1] == "05"
        assert parts[2] == "20"

        # Should end with author ID (first 8 chars)
        assert parts[-1] == "bobsmith"

        # Middle parts should be aspect
        aspect_parts = parts[3:-1]
        assert "machine" in aspect_parts or "learning" in aspect_parts

    def test_empty_aspect_after_colon(self):
        """Handle edge case of title with just author name and colon."""
        slug = _generate_meaningful_slug(title="John: ", window_date="2025-03-15", author_uuid="john-uuid")

        # Should still produce valid slug
        assert slug.startswith("2025-03-15-")
        assert slug.endswith("-john-uui")

    def test_long_aspect_title(self):
        """Handle very long aspect titles gracefully."""
        long_title = (
            "John: " + "A" * 200
        )  # Very long aspect
        slug = _generate_meaningful_slug(title=long_title, window_date="2025-03-15", author_uuid="john-uuid")

        # Should still produce valid slug (slugify should handle long strings)
        assert slug.startswith("2025-03-15-")
        assert slug.endswith("-john-uui")
        assert "a" * 50 in slug  # Should contain many 'a's from the long title


class TestAppendOnlyBehavior:
    """Test that profile system supports append-only architecture."""

    def test_different_slugs_for_same_author_different_analyses(self):
        """Multiple analyses of same author should produce different slugs."""
        author_uuid = "same-author-123"

        # Simulate three different profile analyses
        slug1 = _generate_meaningful_slug(
            title="Technical Skills", window_date="2025-03-01", author_uuid=author_uuid
        )

        slug2 = _generate_meaningful_slug(
            title="Photography Interests", window_date="2025-03-15", author_uuid=author_uuid
        )

        slug3 = _generate_meaningful_slug(
            title="Community Engagement", window_date="2025-04-01", author_uuid=author_uuid
        )

        # All should be unique (append-only)
        assert len({slug1, slug2, slug3}) == 3

    def test_temporal_ordering_via_date_prefix(self):
        """Date prefix enables temporal ordering of profile posts."""
        author_uuid = "author-123"

        slugs = [
            _generate_meaningful_slug(title="Analysis", window_date="2025-01-15", author_uuid=author_uuid),
            _generate_meaningful_slug(title="Analysis", window_date="2025-03-15", author_uuid=author_uuid),
            _generate_meaningful_slug(title="Analysis", window_date="2025-02-15", author_uuid=author_uuid),
        ]

        # When sorted alphabetically, should be in chronological order
        sorted_slugs = sorted(slugs)

        assert sorted_slugs[0].startswith("2025-01-15-")
        assert sorted_slugs[1].startswith("2025-02-15-")
        assert sorted_slugs[2].startswith("2025-03-15-")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
