import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


def test_preview_docs_command():
    """Test the preview-docs command."""
    with patch("subprocess.run") as mock_run:
        result = runner.invoke(app, ["preview-docs"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["mkdocs", "serve", "-f", ".egregora/mkdocs.yml"], check=True
        )


def test_preview_docs_command_with_custom_config():
    """Test the preview-docs command with a custom config file."""
    with patch("subprocess.run") as mock_run:
        result = runner.invoke(app, ["preview-docs", "--config-file", "my-docs/mkdocs.yml"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["mkdocs", "serve", "-f", "my-docs/mkdocs.yml"], check=True
        )

def test_preview_docs_command_file_not_found():
    """Test the preview-docs command when mkdocs is not installed."""
    with patch("subprocess.run", side_effect=FileNotFoundError) as mock_run:
        result = runner.invoke(app, ["preview-docs"])
        assert result.exit_code == 0
        assert "Error: 'mkdocs' command not found." in result.stdout

def test_preview_docs_command_called_process_error():
    """Test the preview-docs command when mkdocs fails."""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "mkdocs")) as mock_run:
        result = runner.invoke(app, ["preview-docs"])
        assert result.exit_code == 0
        assert "Error running mkdocs serve" in result.stdout
