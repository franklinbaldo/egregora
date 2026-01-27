from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.database.backend_factory import create_pipeline_database, validate_and_connect_db


@patch("egregora.database.backend_factory.ibis.connect")
@patch("egregora.database.backend_factory.resolve_db_uri")
def test_validate_and_connect_db_success(mock_resolve, mock_connect):
    mock_resolve.return_value = "duckdb:///tmp/test.db"
    mock_connect.return_value = MagicMock()

    uri = "duckdb:///tmp/test.db"
    site_root = Path("/tmp")

    resolved, _conn = validate_and_connect_db(uri, "test_setting", site_root)

    assert resolved == "duckdb:///tmp/test.db"
    mock_resolve.assert_called_once_with(uri, site_root)
    mock_connect.assert_called_once_with("duckdb:///tmp/test.db")


def test_validate_and_connect_db_empty_value():
    with pytest.raises(ValueError, match="must be a non-empty connection URI"):
        validate_and_connect_db("", "test_setting", Path("/tmp"))


def test_validate_and_connect_db_no_scheme():
    with pytest.raises(ValueError, match="must be provided as an Ibis-compatible connection URI"):
        validate_and_connect_db("invalid_uri", "test_setting", Path("/tmp"))


def test_validate_and_connect_db_looks_like_path():
    with pytest.raises(ValueError, match="looks like a filesystem path"):
        validate_and_connect_db("C:/path/to/db", "test_setting", Path("/tmp"))


@patch("egregora.database.backend_factory.validate_and_connect_db")
def test_create_pipeline_database(mock_validate):
    mock_validate.return_value = ("resolved_uri", MagicMock())

    config = MagicMock()
    config.database.pipeline_db = "duckdb:///tmp/pipeline.db"
    site_root = Path("/tmp")

    create_pipeline_database(site_root, config)

    mock_validate.assert_called_once_with("duckdb:///tmp/pipeline.db", "database.pipeline_db", site_root)
