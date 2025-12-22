
from unittest.mock import MagicMock, patch

import duckdb
import pytest

from egregora.database.duckdb_manager import DuckDBStorageManager


def test_from_ibis_backend_handles_duckdb_error_gracefully():
    """Tests that DuckDBStorageManager.from_ibis_backend handles a duckdb.Error
    during the PRAGMA database_list call and sets db_path to None.
    """
    # 1. Create a mock Ibis backend
    mock_backend = MagicMock()

    # 2. Create a mock DuckDB connection
    mock_connection = MagicMock()

    # 3. Configure the execute method to raise a duckdb.Error
    mock_connection.execute.side_effect = duckdb.Error("Test Exception: Simulating a DB error")

    # 4. Assign the mock connection to the backend's 'con' attribute
    mock_backend.con = mock_connection

    # 5. Call the method under test
    storage_manager = DuckDBStorageManager.from_ibis_backend(mock_backend)

    # 6. Assert that db_path is None, as the exception should be caught
    assert storage_manager.db_path is None


@patch("ibis.duckdb.connect")
def test_reset_connection_handles_duckdb_error(mock_connect):
    """Tests that _reset_connection handles a duckdb.Error during reconnect
    and falls back to an in-memory database.
    """
    # 1. Configure the mock to raise a duckdb.Error, but only after the first call
    mock_connect.side_effect = [
        MagicMock(), # Initial successful connection
        duckdb.Error("Test Exception: Simulating a DB error on reconnect"),
        MagicMock() # Successful in-memory connection
    ]

    # 2. Instantiate the manager
    storage_manager = DuckDBStorageManager(db_path="test.db")

    # 3. Manually set a mock connection to be closed
    storage_manager._conn = MagicMock()

    # 4. Call the method under test
    storage_manager._reset_connection()

    # 5. Assert that the db_path is now None (in-memory)
    assert storage_manager.db_path is None


@patch("ibis.duckdb.connect")
@patch("pathlib.Path.unlink")
def test_reset_connection_handles_os_error_on_unlink(mock_unlink, mock_connect):
    """Tests that _reset_connection handles an OSError during file deletion
    and still falls back to an in-memory database.
    """
    # 1. Configure mocks to allow instantiation, then fail during reset
    mock_connect.side_effect = [
        MagicMock(),  # Succeeds for __init__
        duckdb.Error("database has been invalidated"),  # Fails for the first _connect() in _reset_connection
        MagicMock(),  # Succeeds for the in-memory fallback
    ]
    mock_unlink.side_effect = OSError("Test Exception: Permission denied")

    # 2. Instantiate the manager
    storage_manager = DuckDBStorageManager(db_path="test.db")
    storage_manager._conn = MagicMock()
    # Mock the error check to ensure the correct path is taken
    storage_manager._is_invalidated_error = lambda exc: "invalidated" in str(exc)

    # 3. Call the method under test
    storage_manager._reset_connection()

    # 4. Assert that it fell back to in-memory and did not raise an exception
    assert storage_manager.db_path is None
    mock_unlink.assert_called_once()


@patch("ibis.duckdb.connect")
def test_reset_connection_raises_runtime_error_on_critical_failure(mock_connect):
    """Tests that _reset_connection raises a RuntimeError if it can't even connect
    to an in-memory database.
    """
    # 1. Configure mock to succeed on instantiation, then always fail
    mock_connect.side_effect = [
        MagicMock(),  # Successful instantiation
        duckdb.Error("Test Exception: Persistent DB error"),  # Fails on file-based reconnect
        duckdb.Error("Test Exception: Persistent DB error"),  # Fails on in-memory fallback
    ]

    # 2. Instantiate the manager
    storage_manager = DuckDBStorageManager(db_path="test.db")
    storage_manager._conn = MagicMock()

    # 3. Call the method under test and assert it raises a RuntimeError
    with pytest.raises(RuntimeError, match="Critical failure"):
        storage_manager._reset_connection()
