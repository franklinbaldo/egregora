import subprocess
from unittest.mock import patch

from egregora.cli.main import _run_mkdocs_serve


def test_run_mkdocs_serve(tmp_path):
    """Test the _run_mkdocs_serve helper function."""
    with patch("subprocess.run") as mock_run:
        config_file = tmp_path / "mkdocs.yml"
        config_file.touch()
        _run_mkdocs_serve(config_file)
        mock_run.assert_called_once_with(["mkdocs", "serve", "-f", str(config_file)], check=True)


def test_run_mkdocs_serve_file_not_found(tmp_path):
    """Test the _run_mkdocs_serve helper function when mkdocs is not installed."""
    with patch("subprocess.run", side_effect=FileNotFoundError) as mock_run:
        _run_mkdocs_serve(tmp_path / "mkdocs.yml")
        assert mock_run.called


def test_run_mkdocs_serve_called_process_error(tmp_path):
    """Test the _run_mkdocs_serve helper function when mkdocs fails."""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "mkdocs")) as mock_run:
        _run_mkdocs_serve(tmp_path / "mkdocs.yml")
        assert mock_run.called
