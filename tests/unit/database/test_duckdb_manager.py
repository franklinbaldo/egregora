from unittest.mock import MagicMock, patch

import duckdb
import pytest

from egregora.database.duckdb_manager import DuckDBStorageManager, temp_storage
from egregora.database.exceptions import (
    InvalidOperationError,
    InvalidTableNameError,
    SequenceCreationError,
    SequenceFetchError,
    SequenceNotFoundError,
    SequenceRetryFailedError,
    TableInfoError,
    TableNotFoundError,
)


def test_get_table_columns_raises_table_info_error(mocker):
    """Tests that get_table_columns raises TableInfoError on a database error."""
    with DuckDBStorageManager() as storage:
        # Mock the connection object itself to avoid patching a read-only attribute
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = duckdb.Error("Simulated DB error")
        mocker.patch.object(storage, "_conn", mock_conn)

        with pytest.raises(TableInfoError) as exc_info:
            storage.get_table_columns("any_table")

        assert exc_info.value.table_name == "any_table"


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
        MagicMock(),  # Initial successful connection
        duckdb.Error("Test Exception: Simulating a DB error on reconnect"),
        MagicMock(),  # Successful in-memory connection
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


def test_read_table_not_found():
    """Test that read_table raises TableNotFoundError for a non-existent table."""
    with DuckDBStorageManager() as storage:
        with pytest.raises(TableNotFoundError):
            storage.read_table("non_existent_table")


def test_get_sequence_state_not_found():
    """Test that get_sequence_state raises SequenceNotFoundError for a non-existent sequence."""
    with DuckDBStorageManager() as storage:
        with pytest.raises(SequenceNotFoundError):
            storage.get_sequence_state("non_existent_sequence")


def test_replace_rows_no_keys():
    """Test that replace_rows raises InvalidOperationError when no keys are provided."""
    with DuckDBStorageManager() as storage:
        with pytest.raises(InvalidOperationError):
            storage.replace_rows("some_table", None, by_keys={})


def test_write_table_append_no_checkpoint():
    """Test that write_table raises InvalidOperationError for append mode without checkpoint."""
    with DuckDBStorageManager() as storage:
        with pytest.raises(InvalidOperationError):
            storage.write_table(None, "some_table", mode="append", checkpoint=False)


def test_persist_atomic_invalid_name():
    """Test that persist_atomic raises InvalidTableNameError for an invalid table name."""
    with DuckDBStorageManager() as storage:
        with pytest.raises(InvalidTableNameError):
            storage.persist_atomic(None, "invalid-table-name", None)


def test_sync_sequence_with_table_sequence_not_found(mocker):
    """Test that sync_sequence_with_table raises SequenceNotFoundError if the sequence doesn't exist."""
    with DuckDBStorageManager() as storage:
        # Create a dummy table to prevent CatalogException
        storage.execute_sql("CREATE TABLE some_table (id INTEGER)")
        storage.execute_sql("INSERT INTO some_table VALUES (1)")
        mocker.patch.object(
            storage, "get_sequence_state", side_effect=SequenceNotFoundError("non_existent_sequence")
        )
        with pytest.raises(SequenceNotFoundError):
            storage.sync_sequence_with_table("non_existent_sequence", table="some_table", column="id")


def test_next_sequence_values_invalid_count():
    """Test that next_sequence_values raises InvalidOperationError for a non-positive count."""
    with DuckDBStorageManager() as storage:
        with pytest.raises(InvalidOperationError):
            storage.next_sequence_values("some_sequence", count=0)


def test_next_sequence_values_raises_fetch_error(mocker):
    """Test that next_sequence_values raises SequenceFetchError when fetchone returns None."""
    with DuckDBStorageManager() as storage:
        storage.ensure_sequence("test_sequence")

<<<<<<< HEAD
        # Replace the real connection with a mock since we can't patch C-extension methods
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
<<<<<<< HEAD
        mock_conn.execute.return_value = mock_cursor

        # We need to keep the original connection for ensure_sequence to work above,
        # but for the call under test, we swap it.
        storage._conn = mock_conn
=======
        # Mock the connection's execute method directly since storage.execute is removed
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mocker.patch.object(storage, "_conn", mock_conn)
>>>>>>> origin/pr/2890
=======
        # Replace the real connection with a mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mocker.patch.object(storage, "_conn", mock_conn)
>>>>>>> origin/pr/2877

        with pytest.raises(SequenceFetchError) as exc_info:
            storage.next_sequence_values("test_sequence")
        assert exc_info.value.sequence_name == "test_sequence"


def test_next_sequence_values_raises_retry_failed_error(mocker):
    """Test next_sequence_values raises SequenceRetryFailedError after a failed retry."""
    with DuckDBStorageManager() as storage:
        storage.ensure_sequence("test_sequence")
        mocker.patch.object(storage, "_is_invalidated_error", return_value=True)
<<<<<<< HEAD
<<<<<<< HEAD
        # Prevent reset from replacing our mock
        mocker.patch.object(storage, "_reset_connection")

        # Replace the real connection with a mock
        mock_conn = MagicMock()

        # 1. Fail first fetch
        # 2. Succeed check (returns a mock cursor that has fetchone returning a row)
        # 3. Fail retry fetch

        cursor_success = MagicMock()
        cursor_success.fetchone.return_value = (1, 1, 1)  # Valid sequence state

        mock_conn.execute.side_effect = [
            duckdb.Error("DB error 1"),
            cursor_success,
            duckdb.Error("DB error 2"),
        ]
        storage._conn = mock_conn
=======
        # Mock _reset_connection to prevent it from replacing our mock connection
        mocker.patch.object(storage, "_reset_connection")

        # Mock the connection to fail repeatedly
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = duckdb.Error("DB error")
        mocker.patch.object(storage, "_conn", mock_conn)

        # Mock get_sequence_state to avoid it failing with the same DB error during recovery
        mocker.patch.object(storage, "get_sequence_state")
>>>>>>> origin/pr/2890
=======

        # Mock _reset_connection to prevent it from replacing our failing mock connection
        mocker.patch.object(storage, "_reset_connection")
        # Also mock get_sequence_state/ensure_sequence called during recovery logic
        mocker.patch.object(storage, "get_sequence_state", side_effect=SequenceNotFoundError("test_sequence"))
        mocker.patch.object(storage, "ensure_sequence")

        # Replace the real connection with a mock that raises Error
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = duckdb.Error("DB error")
        mocker.patch.object(storage, "_conn", mock_conn)
>>>>>>> origin/pr/2877

        with pytest.raises(SequenceRetryFailedError) as exc_info:
            storage.next_sequence_values("test_sequence")
        assert exc_info.value.sequence_name == "test_sequence"


def test_ensure_sequence_raises_creation_error_on_verification_failure(mocker):
    """Test ensure_sequence raises SequenceCreationError if verification fails."""
    with DuckDBStorageManager() as storage:
        # Mock get_sequence_state to fail verification after the CREATE call
        mocker.patch.object(storage, "get_sequence_state", side_effect=SequenceNotFoundError("test_sequence"))

        with pytest.raises(SequenceCreationError) as exc_info:
            storage.ensure_sequence("test_sequence")
        assert exc_info.value.sequence_name == "test_sequence"


def test_get_table_columns_raises_table_not_found_for_missing_table():
    """get_table_columns should raise TableNotFoundError for a non-existent table."""
    storage = temp_storage()
    with pytest.raises(TableNotFoundError):
        storage.get_table_columns("non_existent_table")
