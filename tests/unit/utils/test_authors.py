"""Unit tests for author management utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from egregora.utils.authors import (
    extract_authors_from_post,
    load_authors_yml,
    save_authors_yml,
    sync_authors_from_posts,
)
from egregora.utils.exceptions import (
    AuthorsFileError,
    AuthorsFileIOError,
    AuthorsFileParseError,
    PostParseError,
)


def test_load_authors_yml_raises_on_missing_file(tmp_path: Path):
    """Should raise AuthorsFileError if the file doesn't exist."""
    non_existent_file = tmp_path / ".authors.yml"
    with pytest.raises(AuthorsFileError):
        load_authors_yml(non_existent_file)


def test_load_authors_yml_raises_on_invalid_yaml(tmp_path: Path):
    """Should raise AuthorsFileParseError for malformed YAML."""
    authors_file = tmp_path / ".authors.yml"
    authors_file.write_text("not: valid: yaml:")
    with pytest.raises(AuthorsFileParseError):
        load_authors_yml(authors_file)


def test_load_authors_yml_success(tmp_path: Path):
    """Should return a dictionary for valid YAML."""
    authors_file = tmp_path / ".authors.yml"
    authors_data = {"author1": {"name": "Author One"}}
    authors_file.write_text(yaml.dump(authors_data))
    assert load_authors_yml(authors_file) == authors_data


def test_save_authors_yml_raises_on_io_error(tmp_path: Path):
    """Should raise AuthorsFileIOError on file write failure."""
    authors_file = tmp_path / ".authors.yml"
    authors_data = {"author1": {"name": "Author One"}}
    with patch("pathlib.Path.write_text", side_effect=OSError("Disk full")):
        with pytest.raises(AuthorsFileIOError):
            save_authors_yml(authors_file, authors_data, 1)


def test_extract_authors_from_post_raises_on_io_error(tmp_path: Path):
    """Should raise PostParseError on file read failure."""
    post_file = tmp_path / "post.md"
    with patch("frontmatter.load", side_effect=OSError("Permission denied")):
        with pytest.raises(PostParseError):
            extract_authors_from_post(post_file)


def test_sync_authors_from_posts_handles_parse_error(tmp_path: Path):
    """Should not crash if a post file fails to parse."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    posts_dir = docs_dir / "posts"
    posts_dir.mkdir()
    authors_file = docs_dir / ".authors.yml"
    authors_file.touch()

    good_post = posts_dir / "good_post.md"
    good_post.write_text("---\nauthors: [author1]\n---\n")

    # This post will "fail" to parse
    bad_post = posts_dir / "bad_post.md"
    bad_post.write_text("this post is bad")

    # Mock extract_authors_from_post to control failures
    original_extract = extract_authors_from_post

    def mock_extract(md_file: Path):
        if "bad_post" in str(md_file):
            msg = f"mock error for {md_file}"
            raise PostParseError(msg)
        return original_extract(md_file)

    with patch("egregora.utils.authors.extract_authors_from_post", side_effect=mock_extract) as mock:
        new_count = sync_authors_from_posts(posts_dir)
        assert mock.call_count == 2

    assert new_count == 1
    authors_data = yaml.safe_load(authors_file.read_text())
    assert "author1" in authors_data
