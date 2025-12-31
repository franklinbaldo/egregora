"""Unit tests for author management utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.utils.authors import (
    AuthorExtractionError,
    AuthorsFileLoadError,
    AuthorsFileParseError,
    AuthorsFileSaveError,
    extract_authors_from_post,
    load_authors_yml,
    save_authors_yml,
)


def test_load_authors_yml_raises_on_os_error():
    """Should raise AuthorsFileLoadError if the file cannot be read."""
    mock_path = MagicMock(spec=Path)
    mock_path.read_text.side_effect = OSError("File not found")

    with pytest.raises(AuthorsFileLoadError):
        load_authors_yml(mock_path)


def test_load_authors_yml_raises_on_yaml_error():
    """Should raise AuthorsFileParseError if the YAML is malformed."""
    mock_path = MagicMock(spec=Path)
    mock_path.read_text.return_value = "invalid: yaml:"

    with pytest.raises(AuthorsFileParseError):
        load_authors_yml(mock_path)


def test_save_authors_yml_raises_on_os_error():
    """Should raise AuthorsFileSaveError if the file cannot be written."""
    mock_path = MagicMock(spec=Path)
    mock_path.write_text.side_effect = OSError("Permission denied")

    with pytest.raises(AuthorsFileSaveError):
        save_authors_yml(mock_path, {"author1": {}}, 1)


def test_extract_authors_from_post_raises_on_os_error():
    """Should raise AuthorExtractionError if the post file cannot be read."""
    mock_file = MagicMock(spec=Path)
    mock_file.read_text.side_effect = OSError("File not found")

    with patch("frontmatter.load", side_effect=OSError("File not found")):
        with pytest.raises(AuthorExtractionError):
            extract_authors_from_post(mock_file)
