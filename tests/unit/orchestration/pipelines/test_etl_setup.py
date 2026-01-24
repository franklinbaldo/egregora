from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.config.settings import EgregoraConfig
from egregora.orchestration.pipelines.etl.setup import (
    _create_database_backend,
    _validate_and_connect,
    ensure_site_initialized,
)


def test_create_database_backend_raises_value_error_on_empty_uri():
    """Verify that _create_database_backend raises ValueError for an empty database URI."""
    mock_config = MagicMock(spec=EgregoraConfig)
    mock_config.database = MagicMock()
    mock_config.database.pipeline_db = ""

    with pytest.raises(ValueError, match="must be a non-empty connection URI"):
        _create_database_backend(Path("/tmp"), mock_config)


def test_validate_and_connect_success(tmp_path):
    """Verify that _validate_and_connect returns a connection for a valid URI."""
    uri = "duckdb://:memory:"
    resolved, con = _validate_and_connect(uri, "test_setting", tmp_path)
    assert resolved == uri
    assert con is not None


def test_validate_and_connect_missing_scheme(tmp_path):
    """Verify that ValueError is raised if the scheme is missing."""
    uri = "/path/to/db.duckdb"
    with pytest.raises(ValueError, match="must be provided as an Ibis-compatible connection URI"):
        _validate_and_connect(uri, "test_setting", tmp_path)


def test_validate_and_connect_looks_like_path(tmp_path):
    """Verify that ValueError is raised if it looks like a Windows path or similar."""
    uri = "C:/path/to/db"
    with pytest.raises(ValueError, match="looks like a filesystem path"):
        _validate_and_connect(uri, "test_setting", tmp_path)


def test_create_database_backend_integration(tmp_path):
    """Verify _create_database_backend calls _validate_and_connect."""
    mock_config = MagicMock(spec=EgregoraConfig)
    mock_config.database = MagicMock()
    mock_config.database.pipeline_db = "duckdb://:memory:"

    uri, backend = _create_database_backend(tmp_path, mock_config)
    assert uri == "duckdb://:memory:"
    assert backend is not None


@patch("egregora.orchestration.pipelines.etl.setup.MkDocsSiteScaffolder")
def test_ensure_site_initialized_exists(mock_scaffolder, tmp_path):
    """Verify scaffolding is skipped if config exists."""
    output_dir = tmp_path / "site"
    output_dir.mkdir()
    (output_dir / ".egregora.toml").touch()

    ensure_site_initialized(output_dir)
    mock_scaffolder.assert_not_called()


@patch("egregora.orchestration.pipelines.etl.setup.MkDocsSiteScaffolder")
def test_ensure_site_initialized_creates(mock_scaffolder, tmp_path):
    """Verify scaffolding is called if config missing."""
    output_dir = tmp_path / "new_site"

    ensure_site_initialized(output_dir)

    assert output_dir.exists()
    mock_scaffolder.return_value.scaffold_site.assert_called_once_with(output_dir, site_name="new_site")
