from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from egregora.output_adapters.mkdocs.markdown import (
    DirectoryCreationError,
    FileWriteError,
    MissingMetadataError,
    UniqueFilenameError,
    _prepare_frontmatter,
    _resolve_filepath,
    _validate_post_metadata,
    write_markdown_post,
)


@pytest.fixture
def valid_metadata():
    return {
        "title": "Test Post",
        "slug": "test-post",
        "date": datetime(2023, 1, 15, 10, 0, tzinfo=UTC),
        "authors": ["Author One"],
        "tags": ["tag1", "tag2"],
    }


class TestMarkdownHelpers:
    def test_prepare_frontmatter(self, valid_metadata):
        slug = "final-slug"
        fm = _prepare_frontmatter(valid_metadata, slug)

        assert fm["slug"] == slug
        assert fm["title"] == "Test Post"
        assert fm["date"] == "2023-01-15 10:00"
        assert fm["authors"] == ["Author One"]

    def test_validate_metadata_success(self, valid_metadata):
        _validate_post_metadata(valid_metadata)

    def test_validate_metadata_missing_keys(self):
        metadata = {"title": "No Slug or Date"}
        with pytest.raises(MissingMetadataError) as exc:
            _validate_post_metadata(metadata)
        assert "slug" in str(exc.value)
        assert "date" in str(exc.value)

    def test_resolve_filepath_unique(self, tmp_path):
        # Given
        output_dir = tmp_path

        # When
        path, slug = _resolve_filepath(output_dir, "2023-01-15", "base-slug")

        # Then
        assert path == output_dir / "2023-01-15-base-slug.md"
        assert slug == "base-slug"

    def test_resolve_filepath_collision(self, tmp_path):
        # Given
        output_dir = tmp_path
        (output_dir / "2023-01-15-base-slug.md").touch()

        # When
        path, slug = _resolve_filepath(output_dir, "2023-01-15", "base-slug")

        # Then
        assert path == output_dir / "2023-01-15-base-slug-2.md"
        assert slug == "base-slug-2"

    def test_resolve_filepath_exhausted(self, tmp_path):
        # Given
        output_dir = tmp_path
        (output_dir / "2023-01-15-base-slug.md").touch()
        (output_dir / "2023-01-15-base-slug-2.md").touch()

        # When / Then
        with pytest.raises(UniqueFilenameError):
            _resolve_filepath(output_dir, "2023-01-15", "base-slug", max_attempts=1)


class TestWriteMarkdownPost:
    @patch("egregora.output_adapters.mkdocs.markdown.ensure_author_entries")
    def test_write_markdown_post_success(self, mock_ensure_authors, valid_metadata, tmp_path):
        """Test writing a post using real filesystem (tmp_path)."""
        # Given
        content = "## Hello World"
        output_dir = tmp_path / "posts"

        # When
        result_path_str = write_markdown_post(content, valid_metadata, output_dir)
        result_path = Path(result_path_str)

        # Then
        assert result_path.exists()
        assert result_path.parent == output_dir

        # Check content
        text = result_path.read_text(encoding="utf-8")
        assert content in text
        assert "title: Test Post" in text
        assert "slug: test-post" in text

        # Parse YAML frontmatter to be sure
        front, _body = text.split("---\n\n", 1)
        # Remove first ---
        front = front.strip("-").strip()
        data = yaml.safe_load(front)

        assert data["title"] == "Test Post"
        assert data["slug"] == "test-post"

        mock_ensure_authors.assert_called_once()

    def test_write_markdown_post_directory_error(self, valid_metadata):
        # Pass a file as output_dir to trigger mkdir error
        with pytest.raises(DirectoryCreationError):
            # /dev/null is a file, trying to mkdir it fails
            # or just use a non-writable path if we could guarantee it
            # mocking is safer for error injection
            mock_path = MagicMock(spec=Path)
            mock_path.mkdir.side_effect = OSError("Permission denied")
            write_markdown_post("Content", valid_metadata, mock_path)

    @patch("egregora.output_adapters.mkdocs.markdown.ensure_author_entries")
    def test_write_post_file_error(self, mock_ensure_authors, valid_metadata, tmp_path):
        # To simulate file write error with real paths is hard (disk full).
        # So we can patch _write_post_file just for this error case,
        # OR patch Path.write_text.

        with patch("pathlib.Path.write_text", side_effect=OSError("Disk failure")):
            with pytest.raises(FileWriteError):
                write_markdown_post("Content", valid_metadata, tmp_path)
