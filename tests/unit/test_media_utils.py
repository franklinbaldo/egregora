"""Unit tests for media processing utilities."""

import tempfile
from pathlib import Path

import ibis

from egregora.pipeline.media import (
    extract_markdown_media_refs,
    replace_markdown_media_refs,
)
from egregora.sources.base import InputAdapter


class TestExtractMarkdownMediaRefs:
    """Test extraction of markdown media references from messages."""

    def test_extract_image_references(self):
        """Test extracting image references."""
        table = ibis.memtable(
            [
                {"message": "Check this ![photo](IMG-001.jpg)"},
                {"message": "Another ![image](IMG-002.png)"},
            ]
        )

        refs = extract_markdown_media_refs(table)

        assert refs == {"IMG-001.jpg", "IMG-002.png"}

    def test_extract_link_references(self):
        """Test extracting non-image link references."""
        table = ibis.memtable(
            [
                {"message": "Watch [video](VID-001.mp4)"},
                {"message": "Listen [audio](AUD-001.opus)"},
            ]
        )

        refs = extract_markdown_media_refs(table)

        assert refs == {"VID-001.mp4", "AUD-001.opus"}

    def test_extract_mixed_references(self):
        """Test extracting both images and links."""
        table = ibis.memtable(
            [
                {"message": "Photo ![img](IMG-001.jpg) and [video](VID-001.mp4)"},
            ]
        )

        refs = extract_markdown_media_refs(table)

        assert refs == {"IMG-001.jpg", "VID-001.mp4"}

    def test_exclude_http_urls(self):
        """Test that HTTP/HTTPS URLs are excluded."""
        table = ibis.memtable(
            [
                {"message": "[Link](https://example.com) and ![img](photo.jpg)"},
            ]
        )

        refs = extract_markdown_media_refs(table)

        assert refs == {"photo.jpg"}
        assert "https://example.com" not in refs

    def test_extract_with_empty_messages(self):
        """Test extraction with empty or None messages."""
        table = ibis.memtable(
            [
                {"message": "![img](photo.jpg)"},
                {"message": ""},
                {"message": None},
            ]
        )

        refs = extract_markdown_media_refs(table)

        assert refs == {"photo.jpg"}

    def test_deduplicate_references(self):
        """Test that duplicate references are deduplicated."""
        table = ibis.memtable(
            [
                {"message": "![img](photo.jpg)"},
                {"message": "Another ![img2](photo.jpg)"},
                {"message": "[link](photo.jpg)"},
            ]
        )

        refs = extract_markdown_media_refs(table)

        assert refs == {"photo.jpg"}


class TestGenerateContentUUID:
    """Test content-based UUID generation."""

    def test_same_content_same_uuid(self):
        """Test that identical content produces identical UUID."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f1:
            f1.write(b"test content")
            path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f2:
            f2.write(b"test content")
            path2 = Path(f2.name)

        try:
            uuid1 = InputAdapter.generate_media_uuid(path1)
            uuid2 = InputAdapter.generate_media_uuid(path2)

            assert uuid1 == uuid2
        finally:
            path1.unlink()
            path2.unlink()

    def test_different_content_different_uuid(self):
        """Test that different content produces different UUID."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f1:
            f1.write(b"content A")
            path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f2:
            f2.write(b"content B")
            path2 = Path(f2.name)

        try:
            uuid1 = InputAdapter.generate_media_uuid(path1)
            uuid2 = InputAdapter.generate_media_uuid(path2)

            assert uuid1 != uuid2
        finally:
            path1.unlink()
            path2.unlink()

    def test_uuid_format(self):
        """Test that generated UUID has correct format."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            path = Path(f.name)

        try:
            uuid = InputAdapter.generate_media_uuid(path)

            # UUID format: 8-4-4-4-12 hex characters
            assert len(uuid) == 36
            assert uuid.count("-") == 4
        finally:
            path.unlink()


class TestReplaceMarkdownMediaRefs:
    """Test replacement of markdown media references."""

    def test_replace_image_reference(self):
        """Test replacing image markdown reference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            posts_dir = docs_dir / "posts"
            media_dir = docs_dir / "media"

            docs_dir.mkdir()
            posts_dir.mkdir()
            media_dir.mkdir()

            # Create a fake media file
            media_file = media_dir / "abc123.jpg"
            media_file.write_bytes(b"fake image")

            table = ibis.memtable(
                [
                    {"message": "Check this ![photo](IMG-001.jpg)"},
                ]
            )

            mapping = {"IMG-001.jpg": media_file}
            updated = replace_markdown_media_refs(table, mapping, docs_dir, posts_dir)

            result = updated.execute()
            # Should create relative path from posts to media
            assert "../media/abc123.jpg" in result["message"][0]

    def test_replace_link_reference(self):
        """Test replacing link markdown reference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            posts_dir = docs_dir / "posts"
            media_dir = docs_dir / "media"

            docs_dir.mkdir()
            posts_dir.mkdir()
            media_dir.mkdir()

            # Create a fake media file
            media_file = media_dir / "xyz789.mp4"
            media_file.write_bytes(b"fake video")

            table = ibis.memtable(
                [
                    {"message": "Watch [video](VID-001.mp4)"},
                ]
            )

            mapping = {"VID-001.mp4": media_file}
            updated = replace_markdown_media_refs(table, mapping, docs_dir, posts_dir)

            result = updated.execute()
            assert "../media/xyz789.mp4" in result["message"][0]

    def test_replace_multiple_references(self):
        """Test replacing multiple references in one message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            posts_dir = docs_dir / "posts"
            media_dir = docs_dir / "media"

            docs_dir.mkdir()
            posts_dir.mkdir()
            media_dir.mkdir()

            # Create fake media files
            img_file = media_dir / "abc.jpg"
            img_file.write_bytes(b"fake image")
            vid_file = media_dir / "xyz.mp4"
            vid_file.write_bytes(b"fake video")

            table = ibis.memtable(
                [
                    {"message": "Photo ![img](IMG-001.jpg) and [video](VID-001.mp4)"},
                ]
            )

            mapping = {
                "IMG-001.jpg": img_file,
                "VID-001.mp4": vid_file,
            }
            updated = replace_markdown_media_refs(table, mapping, docs_dir, posts_dir)

            result = updated.execute()
            assert "../media/abc.jpg" in result["message"][0]
            assert "../media/xyz.mp4" in result["message"][0]

    def test_replace_with_empty_mapping(self):
        """Test that empty mapping returns unchanged table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            posts_dir = docs_dir / "posts"

            docs_dir.mkdir()
            posts_dir.mkdir()

            table = ibis.memtable(
                [
                    {"message": "Check this ![photo](IMG-001.jpg)"},
                ]
            )

            updated = replace_markdown_media_refs(table, {}, docs_dir, posts_dir)

            result = updated.execute()
            assert result["message"][0] == "Check this ![photo](IMG-001.jpg)"

    def test_replace_only_matching_references(self):
        """Test that only references in mapping are replaced."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            posts_dir = docs_dir / "posts"
            media_dir = docs_dir / "media"

            docs_dir.mkdir()
            posts_dir.mkdir()
            media_dir.mkdir()

            # Create fake media file
            media_file = media_dir / "abc.jpg"
            media_file.write_bytes(b"fake image")

            table = ibis.memtable(
                [
                    {"message": "![img1](IMG-001.jpg) and ![img2](IMG-002.jpg)"},
                ]
            )

            mapping = {"IMG-001.jpg": media_file}
            updated = replace_markdown_media_refs(table, mapping, docs_dir, posts_dir)

            result = updated.execute()
            assert "../media/abc.jpg" in result["message"][0]
            assert "IMG-002.jpg" in result["message"][0]  # Unchanged
