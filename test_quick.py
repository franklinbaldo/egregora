#!/usr/bin/env python3
"""Quick test to verify sequence exception handling."""

from unittest.mock import MagicMock

import duckdb
import pytest

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.exceptions import SequenceFetchError, SequenceRetryFailedError


def test_fetch_error() -> None:
    """Test that next_sequence_values raises SequenceFetchError when fetchone returns None."""
    with DuckDBStorageManager() as storage:
        storage.ensure_sequence("test_sequence")

        # Mock execute to return a cursor with fetchone() returning None
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        storage.execute = MagicMock(return_value=mock_cursor)

        with pytest.raises(SequenceFetchError) as excinfo:
            storage.next_sequence_values("test_sequence")
        assert excinfo.value.sequence_name == "test_sequence"  # noqa: S101


def test_retry_failed_error() -> None:
    """Test next_sequence_values raises SequenceRetryFailedError after a failed retry."""
    with DuckDBStorageManager() as storage:
        storage.ensure_sequence("test_sequence")

        # Mock _is_invalidated_error to return True
        storage._is_invalidated_error = MagicMock(return_value=True)

        # Mock execute to always raise duckdb.Error
        storage.execute = MagicMock(side_effect=duckdb.Error("DB error"))

        with pytest.raises(SequenceRetryFailedError) as excinfo:
            storage.next_sequence_values("test_sequence")
        assert excinfo.value.sequence_name == "test_sequence"  # noqa: S101


if __name__ == "__main__":
    pytest.main([__file__])
