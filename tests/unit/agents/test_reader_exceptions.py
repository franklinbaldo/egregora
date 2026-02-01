"""Tests for reader agent exceptions."""

import pytest

from egregora.agents.exceptions import (
    ReaderConfigurationError,
    ReaderInputError,
)
from egregora.agents.reader.reader_runner import run_reader_evaluation
from egregora.config.settings import ReaderSettings


@pytest.fixture
def mock_config():
    return ReaderSettings(enabled=True, comparisons_per_post=2, database_path="test_reader.duckdb")


def test_run_reader_evaluation_missing_directory(tmp_path, mock_config):
    """Test that missing posts directory raises ReaderConfigurationError."""
    missing_dir = tmp_path / "non_existent"

    with pytest.raises(ReaderConfigurationError, match="Posts directory not found"):
        run_reader_evaluation(posts_dir=missing_dir, config=mock_config)


def test_run_reader_evaluation_no_posts(tmp_path, mock_config):
    """Test that empty directory raises ReaderInputError."""
    # Create valid but empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(ReaderInputError, match="No posts found"):
        run_reader_evaluation(posts_dir=empty_dir, config=mock_config)


def test_run_reader_evaluation_insufficient_posts(tmp_path, mock_config):
    """Test that single post raises ReaderInputError."""
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir()
    (posts_dir / "post1.md").write_text("content")

    with pytest.raises(ReaderInputError, match="Need at least 2 unique slugs"):
        run_reader_evaluation(posts_dir=posts_dir, config=mock_config)


def test_run_reader_evaluation_disabled(tmp_path, mock_config):
    """Test that disabled config returns empty list."""
    mock_config.enabled = False
    result = run_reader_evaluation(posts_dir=tmp_path, config=mock_config)
    assert result == []
