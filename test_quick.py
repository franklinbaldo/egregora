#!/usr/bin/env python3
"""Quick test to verify sequence exception handling."""

import sys
from unittest.mock import MagicMock

import duckdb

# Add src to path
sys.path.insert(0, "/home/user/egregora/src")

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.exceptions import SequenceFetchError, SequenceRetryFailedError


def test_fetch_error() -> bool | None:
    """Test that next_sequence_values raises SequenceFetchError when fetchone returns None."""
    with DuckDBStorageManager() as storage:
        storage.ensure_sequence("test_sequence")

        # Mock execute to return a cursor with fetchone() returning None
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        storage.execute = MagicMock(return_value=mock_cursor)

        try:
            storage.next_sequence_values("test_sequence")
            return False
        except SequenceFetchError as e:
            return e.sequence_name == "test_sequence"
        except BaseException:
            return False


def test_retry_failed_error() -> bool | None:
    """Test next_sequence_values raises SequenceRetryFailedError after a failed retry."""
    with DuckDBStorageManager() as storage:
        storage.ensure_sequence("test_sequence")

        # Mock _is_invalidated_error to return True
        storage._is_invalidated_error = MagicMock(return_value=True)

        # Mock execute to always raise duckdb.Error
        storage.execute = MagicMock(side_effect=duckdb.Error("DB error"))

        try:
            storage.next_sequence_values("test_sequence")
            return False
        except SequenceRetryFailedError as e:
            return e.sequence_name == "test_sequence"
        except BaseException:
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    results = []
    results.append(test_fetch_error())
    results.append(test_retry_failed_error())

    if all(results):
        sys.exit(0)
    else:
        sys.exit(1)
