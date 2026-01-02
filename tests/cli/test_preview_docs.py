from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


def test_preview_docs_command(tmp_path):
    """Test the preview-docs command."""
    with runner.isolated_filesystem(temp_dir=tmp_path) as temp_dir:
        config_dir = Path(temp_dir) / ".egregora"
        config_dir.mkdir()
        config_file = config_dir / "mkdocs.yml"
        config_file.touch()
        with patch("egregora.cli.main._run_mkdocs_serve") as mock_run:
            result = runner.invoke(app, ["preview-docs", "--config-file", str(config_file)])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(config_file)


def test_preview_docs_command_with_custom_config(tmp_path):
    """Test the preview-docs command with a custom config file."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        config_file = Path("my-docs/mkdocs.yml")
        config_file.parent.mkdir()
        config_file.touch()
        with patch("egregora.cli.main._run_mkdocs_serve") as mock_run:
            result = runner.invoke(app, ["preview-docs", "--config-file", str(config_file)])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(config_file)
