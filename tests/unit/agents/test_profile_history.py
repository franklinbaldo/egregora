"""Behavioral tests for profile history generation.

Tests focus on behavior (what the system does) rather than implementation (how it does it).
Following TDD principles retroactively to ensure comprehensive coverage.
"""

from pathlib import Path

import pytest

from egregora.agents.profile.history import (
    MIN_FILENAME_PARTS,
    ProfilePost,
    get_profile_history_for_context,
    load_profile_posts,
)


class TestProfilePostLoading:
    """Test loading profile posts from filesystem - behavior focused."""

    def test_loads_profile_post_from_valid_file(self, tmp_path: Path):
        """BEHAVIOR: System loads profile posts from markdown files with date-aspect-uuid naming."""
        # Arrange
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2025-01-15-technical-contributions-author-123.md"
        file.write_text("# Technical Contributions\n\nJohn is a Python expert.")

        # Act
        posts = load_profile_posts("author-123", profiles_base)

        # Assert
        assert len(posts) == 1
        assert posts[0].date == "2025-01-15"
        assert posts[0].aspect == "Technical Contributions"
        assert "Python expert" in posts[0].content

    def test_extracts_date_from_filename(self, tmp_path: Path):
        """BEHAVIOR: Date is extracted from first 3 parts of filename (YYYY-MM-DD)."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2024-12-25-holiday-coding-author-123.md"
        file.write_text("# Holiday Coding\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert posts[0].date == "2024-12-25"

    def test_extracts_aspect_from_filename(self, tmp_path: Path):
        """BEHAVIOR: Aspect is extracted from middle parts, converted to Title Case."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        # Multi-word aspect with hyphens
        file = profile_dir / "2025-01-01-community-leadership-skills-author-123.md"
        file.write_text("# Community Leadership Skills\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert posts[0].aspect == "Community Leadership Skills"

    def test_handles_single_word_aspect(self, tmp_path: Path):
        """BEHAVIOR: Single-word aspects are properly extracted."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2025-01-01-contributions-author-123.md"
        file.write_text("# Contributions\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert posts[0].aspect == "Contributions"

    def test_extracts_title_from_content(self, tmp_path: Path):
        """BEHAVIOR: Post title is extracted from first H1 heading."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2025-01-01-test-author-123.md"
        file.write_text("# John's Amazing Work\n\nDetails here...")

        posts = load_profile_posts("author-123", profiles_base)

        assert posts[0].title == "John's Amazing Work"

    def test_extracts_slug_from_filename(self, tmp_path: Path):
        """BEHAVIOR: Slug is the filename without extension."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2025-01-01-test-aspect-author-123.md"
        file.write_text("# Title\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert posts[0].slug == "2025-01-01-test-aspect-author-123"

    def test_loads_multiple_posts_in_chronological_order(self, tmp_path: Path):
        """BEHAVIOR: Multiple posts are loaded and sorted by date (newest first)."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        (profile_dir / "2025-01-01-first-author-123.md").write_text("# First\n\nContent")
        (profile_dir / "2025-01-15-second-author-123.md").write_text("# Second\n\nContent")
        (profile_dir / "2025-01-10-third-author-123.md").write_text("# Third\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert len(posts) == 3
        assert posts[0].date == "2025-01-15"  # Newest first
        assert posts[1].date == "2025-01-10"
        assert posts[2].date == "2025-01-01"  # Oldest last

    def test_ignores_index_files(self, tmp_path: Path):
        """BEHAVIOR: index.md files are ignored (not profile posts)."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        (profile_dir / "index.md").write_text("# Index\n\nThis is an index")
        (profile_dir / "2025-01-01-valid-author-123.md").write_text("# Valid\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert len(posts) == 1
        assert posts[0].slug == "2025-01-01-valid-author-123"

    def test_ignores_non_markdown_files(self, tmp_path: Path):
        """BEHAVIOR: Only .md files are processed."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        (profile_dir / "2025-01-01-test-author-123.txt").write_text("Not markdown")
        (profile_dir / "2025-01-01-valid-author-123.md").write_text("# Valid\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert len(posts) == 1
        assert posts[0].slug == "2025-01-01-valid-author-123"

    def test_handles_missing_directory(self, tmp_path: Path):
        """BEHAVIOR: Returns empty list when directory doesn't exist."""
        profiles_base = tmp_path / "profiles"

        posts = load_profile_posts("nonexistent-author", profiles_base)

        assert posts == []

    def test_handles_empty_directory(self, tmp_path: Path):
        """BEHAVIOR: Returns empty list when directory has no markdown files."""
        profiles_base = tmp_path / "profiles"
        empty_dir = profiles_base / "author-123"
        empty_dir.mkdir(parents=True)

        posts = load_profile_posts("author-123", profiles_base)

        assert posts == []

    def test_handles_malformed_filename_gracefully(self, tmp_path: Path):
        """BEHAVIOR: Files with < 4 parts get fallback date/aspect."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        # Only 2 parts (not enough)
        file = profile_dir / "invalid-file.md"
        file.write_text("# Title\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert len(posts) == 1
        # Fallback values - date will be today
        assert len(posts[0].date) == 10  # YYYY-MM-DD format
        assert posts[0].aspect == "General Profile"

    def test_handles_missing_h1_title(self, tmp_path: Path):
        """BEHAVIOR: Falls back to 'Profile Post' when no H1 found."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2025-01-01-test-author-123.md"
        file.write_text("Content without a title header")

        posts = load_profile_posts("author-123", profiles_base)

        assert posts[0].title == "Profile Post"


class TestProfilePostSummary:
    """Test ProfilePost summary property - behavior focused."""

    def test_summary_returns_first_paragraph(self):
        """BEHAVIOR: Summary is the first non-heading paragraph."""
        post = ProfilePost(
            date="2025-01-01",
            title="Test",
            slug="test",
            content="# Title\n\nFirst paragraph here.\n\nSecond paragraph.",
            file_path=Path("/tmp/test.md"),
            aspect="Test",
        )

        assert post.summary == "First paragraph here."

    def test_summary_skips_headings(self):
        """BEHAVIOR: Summary skips all heading lines."""
        post = ProfilePost(
            date="2025-01-01",
            title="Test",
            slug="test",
            content="# Title\n\n## Subtitle\n\nActual content here.",
            file_path=Path("/tmp/test.md"),
            aspect="Test",
        )

        assert post.summary == "Actual content here."

    def test_summary_handles_empty_content(self):
        """BEHAVIOR: Returns empty string for content with no paragraphs."""
        post = ProfilePost(
            date="2025-01-01",
            title="Test",
            slug="test",
            content="# Only Headings\n\n## No Content",
            file_path=Path("/tmp/test.md"),
            aspect="Test",
        )

        assert post.summary == ""


class TestContextGeneration:
    """Test generating context string for LLM - behavior focused."""

    def test_generates_context_with_recent_posts(self, tmp_path: Path):
        """BEHAVIOR: Context includes recent profile posts for LLM."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        (profile_dir / "2025-01-15-coding-author-123.md").write_text(
            "# John's Coding Skills\n\nJohn is excellent at Python."
        )

        context = get_profile_history_for_context("author-123", profiles_base)

        assert "John's Coding Skills" in context
        assert "Python" in context

    def test_context_respects_max_posts_limit(self, tmp_path: Path):
        """BEHAVIOR: Limits number of posts in context to avoid token bloat."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        # Create 10 posts
        for i in range(10):
            (profile_dir / f"2025-01-{i+1:02d}-post{i}-author-123.md").write_text(f"# Post {i}\n\nContent {i}")

        context = get_profile_history_for_context("author-123", profiles_base, max_posts=3)

        # Should only include 3 most recent
        assert "Post 9" in context  # Most recent (day 10)
        assert "Post 8" in context  # (day 9)
        assert "Post 7" in context  # (day 8)
        assert "Post 0" not in context  # Oldest excluded

    def test_context_includes_metadata_summary(self, tmp_path: Path):
        """BEHAVIOR: Context includes summary metadata (total posts, aspects)."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        (profile_dir / "2025-01-01-coding-author-123.md").write_text("# Coding\n\nContent")
        (profile_dir / "2025-01-15-design-author-123.md").write_text("# Design\n\nContent")

        context = get_profile_history_for_context("author-123", profiles_base)

        # Should mention total posts
        assert "2" in context
        # Should mention aspects
        assert "Coding" in context or "Design" in context

    def test_context_indicates_no_history_exists(self, tmp_path: Path):
        """BEHAVIOR: Returns message when no history exists."""
        profiles_base = tmp_path / "profiles"
        empty_dir = profiles_base / "author-123"
        empty_dir.mkdir(parents=True)

        context = get_profile_history_for_context("author-123", profiles_base)

        # Should indicate no history
        assert "no prior" in context.lower() or "no previous" in context.lower()

    def test_context_handles_missing_directory(self, tmp_path: Path):
        """BEHAVIOR: Gracefully handles nonexistent profile directory."""
        profiles_base = tmp_path / "profiles"

        context = get_profile_history_for_context("nonexistent-author", profiles_base)

        assert "no prior" in context.lower()

    def test_context_shows_aspects_coverage(self, tmp_path: Path):
        """BEHAVIOR: Context summarizes what aspects have been analyzed."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        (profile_dir / "2025-01-01-coding-author-123.md").write_text("# Coding\n\nContent")
        (profile_dir / "2025-01-05-design-author-123.md").write_text("# Design\n\nContent")
        (profile_dir / "2025-01-10-leadership-author-123.md").write_text("# Leadership\n\nContent")

        context = get_profile_history_for_context("author-123", profiles_base)

        # Should list aspects covered
        assert "Coding" in context
        assert "Design" in context
        assert "Leadership" in context

    def test_context_provides_guidelines_for_new_analysis(self, tmp_path: Path):
        """BEHAVIOR: Context includes guidelines for the next profile post."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        (profile_dir / "2025-01-01-coding-author-123.md").write_text("# Coding\n\nContent")

        context = get_profile_history_for_context("author-123", profiles_base)

        # Should include guidelines
        assert "build on" in context.lower() or "avoid repeat" in context.lower()


class TestEdgeCases:
    """Test edge cases and error conditions - behavior focused."""

    def test_handles_unicode_in_content(self, tmp_path: Path):
        """BEHAVIOR: Properly handles Unicode characters in content."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2025-01-01-test-author-123.md"
        file.write_text("# José's Café ☕\n\nÜber cool 中文 content! 🎉")

        posts = load_profile_posts("author-123", profiles_base)

        assert len(posts) == 1
        assert "José" in posts[0].content
        assert "☕" in posts[0].content
        assert "中文" in posts[0].content

    def test_handles_very_long_aspect_names(self, tmp_path: Path):
        """BEHAVIOR: Handles aspect names with many hyphenated words."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2025-01-01-long-multi-word-aspect-name-with-many-parts-author-123.md"
        file.write_text("# Title\n\nContent")

        posts = load_profile_posts("author-123", profiles_base)

        assert posts[0].aspect == "Long Multi Word Aspect Name With Many Parts"

    def test_handles_empty_markdown_file(self, tmp_path: Path):
        """BEHAVIOR: Handles empty markdown files without crashing."""
        profiles_base = tmp_path / "profiles"
        profile_dir = profiles_base / "author-123"
        profile_dir.mkdir(parents=True)

        file = profile_dir / "2025-01-01-test-author-123.md"
        file.write_text("")

        posts = load_profile_posts("author-123", profiles_base)

        assert len(posts) == 1
        assert posts[0].content == ""
        assert posts[0].title == "Profile Post"

    def test_min_filename_parts_constant_matches_logic(self):
        """BEHAVIOR: MIN_FILENAME_PARTS constant reflects actual parsing logic."""
        # This ensures the constant we export matches what we expect
        assert MIN_FILENAME_PARTS == 4  # YYYY-MM-DD-aspect


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
