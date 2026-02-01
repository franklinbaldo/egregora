"""Tests for read command CLI."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from egregora.agents.exceptions import ReaderConfigurationError, ReaderInputError
from egregora.cli.read import read_app

runner = CliRunner()


@pytest.fixture
def site_root(tmp_path):
    """Create a valid site root."""
    (tmp_path / ".egregora").mkdir()
    return tmp_path


def test_read_command_success(site_root):
    """Test successful execution."""
    with (
        patch("egregora.cli.read.load_egregora_config") as mock_load,
        patch("egregora.cli.read.MkDocsPaths") as mock_paths,
        patch("egregora.cli.read.run_reader_evaluation") as mock_run,
    ):
        # Setup config
        mock_config = MagicMock()
        mock_config.reader.enabled = True
        mock_config.reader.comparisons_per_post = 5
        mock_config.reader.k_factor = 32
        mock_load.return_value = mock_config

        # Setup paths
        mock_path_instance = MagicMock()
        mock_path_instance.posts_dir = site_root / "posts"  # Return real path so printing works
        mock_paths.return_value = mock_path_instance

        # Mock result
        mock_result = MagicMock()
        mock_result.rank = 1
        mock_result.post_slug = "test-post"
        mock_result.rating = 1200
        mock_result.comparisons = 5
        mock_result.win_rate = 50.0
        mock_run.return_value = [mock_result]

        result = runner.invoke(read_app, [str(site_root)])

    assert result.exit_code == 0
    assert "Post Quality Rankings" in result.stdout
    assert "test-post" in result.stdout


def test_read_command_input_error(site_root):
    """Test handling of ReaderInputError."""
    with (
        patch("egregora.cli.read.load_egregora_config"),
        patch("egregora.cli.read.MkDocsPaths"),
        patch("egregora.cli.read.run_reader_evaluation") as mock_run,
    ):
        mock_run.side_effect = ReaderInputError("Not enough posts")

        result = runner.invoke(read_app, [str(site_root)])

    assert result.exit_code == 1
    assert "Reader Error" in result.stdout
    assert "Not enough posts" in result.stdout


def test_read_command_config_error(site_root):
    """Test handling of ReaderConfigurationError."""
    with (
        patch("egregora.cli.read.load_egregora_config"),
        patch("egregora.cli.read.MkDocsPaths"),
        patch("egregora.cli.read.run_reader_evaluation") as mock_run,
    ):
        mock_run.side_effect = ReaderConfigurationError("Bad config")

        result = runner.invoke(read_app, [str(site_root)])

    assert result.exit_code == 1
    assert "Reader Error" in result.stdout
    assert "Bad config" in result.stdout
