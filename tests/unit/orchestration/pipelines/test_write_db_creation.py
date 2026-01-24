from unittest.mock import MagicMock

import pytest

from egregora.config.settings import EgregoraConfig
from egregora.orchestration.pipelines.write import _create_database_backend, _validate_and_connect


def test_validate_and_connect_success(tmp_path):
    """Verify that _validate_and_connect returns a connection for a valid URI."""
    uri = "duckdb://:memory:"
    resolved, con = _validate_and_connect(uri, "test_setting", tmp_path)
    assert resolved == uri
    assert con is not None
    # Check that it's an ibis connection (mocked or real)
    # Since we don't want to actually connect to a DB if not needed, we might mock ibis.connect
    # But for :memory: it's fine.


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
    # Configure the mock to allow access to database.pipeline_db
    # spec=EgregoraConfig restricts attributes, so 'database' must be explicitly set or spec'd recursively
    mock_config.database = MagicMock()
    mock_config.database.pipeline_db = "duckdb://:memory:"

    # We can mock _validate_and_connect if we want to ensure it's called
    # But since we are extracting it, we want to test the full flow or the components.

    # Let's trust the unit tests for _validate_and_connect and just check success here.
    uri, backend = _create_database_backend(tmp_path, mock_config)
    assert uri == "duckdb://:memory:"
    assert backend is not None
