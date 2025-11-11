"""Tests for OutputFormat common utilities and data integrity validations.

Verifies that OutputFormat base class utilities work correctly:
- normalize_slug() - URL-safe slug normalization
- extract_date_prefix() - date extraction from various formats
- generate_unique_filename() - prevent silent overwrites
- parse_frontmatter() - YAML frontmatter parsing
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from egregora.rendering.base import OutputFormat
from egregora.rendering.mkdocs import MkDocsOutputFormat


class TestNormalizeSlug:
    """Test OutputFormat.normalize_slug() utility."""

    def test_normalize_slug_lowercase(self):
        """Normalizes to lowercase."""
        result = OutputFormat.normalize_slug("My Great Post")
        assert result == "my-great-post"

    def test_normalize_slug_replaces_spaces(self):
        """Replaces spaces with hyphens."""
        result = OutputFormat.normalize_slug("multiple word slug")
        assert result == "multiple-word-slug"

    def test_normalize_slug_removes_special_chars(self):
        """Removes special characters."""
        result = OutputFormat.normalize_slug("Post with Special! Chars@")
        assert "!" not in result
        assert "@" not in result

    def test_normalize_slug_already_normalized(self):
        """Handles already-normalized slugs."""
        result = OutputFormat.normalize_slug("already-normalized")
        assert result == "already-normalized"

    def test_normalize_slug_unicode(self):
        """Handles unicode characters."""
        result = OutputFormat.normalize_slug("Café and Résumé")
        # Slugify should handle unicode appropriately
        assert " " not in result


class TestExtractDatePrefix:
    """Test OutputFormat.extract_date_prefix() utility."""

    def test_extract_date_prefix_clean_date(self):
        """Extracts clean YYYY-MM-DD dates."""
        result = OutputFormat.extract_date_prefix("2025-01-10")
        assert result == "2025-01-10"

    def test_extract_date_prefix_iso_timestamp(self):
        """Extracts date from ISO timestamps."""
        result = OutputFormat.extract_date_prefix("2025-01-10T14:30:00")
        assert result == "2025-01-10"

    def test_extract_date_prefix_window_label(self):
        """Extracts date from window labels."""
        result = OutputFormat.extract_date_prefix("2025-01-10 10:00 to 12:00")
        assert result == "2025-01-10"

    def test_extract_date_prefix_datetime_string(self):
        """Extracts date from datetime strings."""
        result = OutputFormat.extract_date_prefix("2025-01-10 14:30:45")
        assert result == "2025-01-10"

    def test_extract_date_prefix_empty_string(self):
        """Returns today's date for empty string."""
        result = OutputFormat.extract_date_prefix("")
        expected = datetime.date.today().isoformat()
        assert result == expected

    def test_extract_date_prefix_invalid_format(self):
        """Returns today's date for invalid formats."""
        result = OutputFormat.extract_date_prefix("not a date")
        expected = datetime.date.today().isoformat()
        assert result == expected


class TestGenerateUniqueFilename:
    """Test OutputFormat.generate_unique_filename() utility."""

    def test_generate_unique_filename_no_collision(self, tmp_path: Path):
        """Returns original filename if no collision."""
        result = OutputFormat.generate_unique_filename(tmp_path, "test.md")
        assert result == tmp_path / "test.md"

    def test_generate_unique_filename_adds_suffix(self, tmp_path: Path):
        """Adds suffix if file exists."""
        # Create existing file
        (tmp_path / "test.md").write_text("existing")

        result = OutputFormat.generate_unique_filename(tmp_path, "test.md")
        assert result == tmp_path / "test-2.md"

    def test_generate_unique_filename_increments_suffix(self, tmp_path: Path):
        """Increments suffix for multiple collisions."""
        # Create multiple existing files
        (tmp_path / "test.md").write_text("v1")
        (tmp_path / "test-2.md").write_text("v2")
        (tmp_path / "test-3.md").write_text("v3")

        result = OutputFormat.generate_unique_filename(tmp_path, "test.md")
        assert result == tmp_path / "test-4.md"

    def test_generate_unique_filename_with_suffix_placeholder(self, tmp_path: Path):
        """Uses suffix placeholder if provided."""
        # Create existing file
        (tmp_path / "test.md").write_text("existing")

        result = OutputFormat.generate_unique_filename(tmp_path, "test{suffix}.md")
        assert result == tmp_path / "test-2.md"


class TestParseFrontmatter:
    """Test OutputFormat.parse_frontmatter() utility."""

    def test_parse_frontmatter_with_yaml(self):
        """Parses YAML frontmatter correctly."""
        content = """---
title: Test Post
date: 2025-01-10
tags: [tag1, tag2]
---

Body content here."""

        format_instance = MkDocsOutputFormat()
        metadata, body = format_instance.parse_frontmatter(content)

        assert metadata["title"] == "Test Post"
        # YAML parses dates as datetime.date objects
        assert str(metadata["date"]) == "2025-01-10" or metadata["date"] == datetime.date(2025, 1, 10)
        assert metadata["tags"] == ["tag1", "tag2"]
        assert body.strip() == "Body content here."

    def test_parse_frontmatter_no_frontmatter(self):
        """Returns empty dict for content without frontmatter."""
        content = "Just plain content"

        format_instance = MkDocsOutputFormat()
        metadata, body = format_instance.parse_frontmatter(content)

        assert metadata == {}
        assert body == content

    def test_parse_frontmatter_empty_frontmatter(self):
        """Handles empty frontmatter (treated as no frontmatter)."""
        content = """---
---

Body content."""

        format_instance = MkDocsOutputFormat()
        metadata, body = format_instance.parse_frontmatter(content)

        # Empty frontmatter is treated as no frontmatter (implementation detail)
        # Returns empty dict but preserves the content as-is
        assert metadata == {}
        # Body includes the markers since it wasn't recognized as valid frontmatter
        assert "Body content" in body


class TestMkDocsPostStorageIntegration:
    """Integration tests for MkDocsPostStorage with OutputFormat utilities."""

    def test_write_with_output_format_normalizes_slug(self, tmp_path: Path):
        """write() normalizes slug when output_format provided."""
        output_format = MkDocsOutputFormat()
        output_format.initialize(tmp_path)

        post_storage = output_format.posts
        result = post_storage.write(
            slug="My Post With Spaces",
            metadata={"title": "Test", "date": "2025-01-10"},
            content="Content",
        )

        # Check that filename uses normalized slug
        assert "my-post-with-spaces" in result
        assert " " not in result  # No spaces in filename

    def test_write_with_output_format_adds_date_prefix(self, tmp_path: Path):
        """write() adds date prefix when output_format provided."""
        output_format = MkDocsOutputFormat()
        output_format.initialize(tmp_path)

        post_storage = output_format.posts
        result = post_storage.write(
            slug="test-post",
            metadata={"title": "Test", "date": "2025-01-10"},
            content="Content",
        )

        # Check that filename has date prefix
        assert "2025-01-10" in result
        assert "2025-01-10-test-post" in result

    def test_write_with_output_format_prevents_overwrite(self, tmp_path: Path):
        """write() generates unique filename for duplicate slugs."""
        output_format = MkDocsOutputFormat()
        output_format.initialize(tmp_path)

        post_storage = output_format.posts

        # Write first post
        result1 = post_storage.write(
            slug="duplicate-slug",
            metadata={"title": "Post 1", "date": "2025-01-10"},
            content="Content 1",
        )

        # Write second post with same slug
        result2 = post_storage.write(
            slug="duplicate-slug",
            metadata={"title": "Post 2", "date": "2025-01-10"},
            content="Content 2",
        )

        # Should have different filenames
        assert result1 != result2
        assert "-2.md" in result2  # Second file should have suffix

    def test_write_without_output_format_fallback(self, tmp_path: Path):
        """write() falls back to simple format without output_format."""
        from egregora.rendering.mkdocs import MkDocsPostStorage

        post_storage = MkDocsPostStorage(tmp_path)  # No output_format parameter
        result = post_storage.write(
            slug="simple-post",
            metadata={"title": "Test"},
            content="Content",
        )

        # Should use simple filename format
        assert result == "posts/simple-post.md"

    def test_read_handles_both_formats(self, tmp_path: Path):
        """read() can find posts in both date-prefixed and simple formats."""
        from egregora.rendering.mkdocs import MkDocsPostStorage

        post_storage = MkDocsPostStorage(tmp_path)
        posts_dir = tmp_path / "posts"
        # posts_dir already created by MkDocsPostStorage.__init__

        # Write date-prefixed file
        (posts_dir / "2025-01-10-my-post.md").write_text("---\ntitle: Test\n---\n\nContent")

        # Should be able to read with just the slug
        result = post_storage.read("my-post")
        assert result is not None
        metadata, content = result
        assert metadata["title"] == "Test"
        assert content.strip() == "Content"

    def test_exists_handles_both_formats(self, tmp_path: Path):
        """exists() returns True for both date-prefixed and simple formats."""
        from egregora.rendering.mkdocs import MkDocsPostStorage

        post_storage = MkDocsPostStorage(tmp_path)
        posts_dir = tmp_path / "posts"
        # posts_dir already created by MkDocsPostStorage.__init__

        # Write date-prefixed file
        (posts_dir / "2025-01-10-my-post.md").write_text("content")

        # Should find with just the slug
        assert post_storage.exists("my-post") is True
        assert post_storage.exists("nonexistent") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
