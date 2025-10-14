"""Tests for the archive module."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from egregora.archive.main import app

runner = CliRunner()


@patch("egregora.archive.main.search_items")
@patch("egregora.archive.main.download")
def test_download_command(mock_download, mock_search_items):
    """Tests the download command."""
    mock_search_items.return_value = [type("Item", (), {"identifier": "test-item"})()]
    result = runner.invoke(app, ["download"])
    assert result.exit_code == 0
    mock_search_items.assert_called_once()
    mock_download.assert_called_once_with("test-item", verbose=True)


@patch("egregora.archive.main.upload")
def test_upload_command(mock_upload, tmp_path):
    """Tests the upload command."""
    parquet_file = tmp_path / "test.parquet"
    parquet_file.touch()
    result = runner.invoke(app, ["upload", str(parquet_file)])
    assert result.exit_code == 0
    mock_upload.assert_called_once()
