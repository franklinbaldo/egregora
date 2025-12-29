#!/usr/bin/env python
"""Quick test to verify sequence exception handling."""
import sys
from unittest.mock import MagicMock
import duckdb

# Add src to path
sys.path.insert(0, '/home/user/egregora/src')

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.exceptions import SequenceFetchError, SequenceRetryFailedError

def test_fetch_error():
    """Test that next_sequence_values raises SequenceFetchError when fetchone returns None."""
    print("Testing SequenceFetchError...")
    with DuckDBStorageManager() as storage:
        storage.ensure_sequence("test_sequence")

        # Mock execute to return a cursor with fetchone() returning None
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        original_execute = storage.execute
        storage.execute = MagicMock(return_value=mock_cursor)

        try:
            storage.next_sequence_values("test_sequence")
            print("  FAILED: No exception raised")
            return False
        except SequenceFetchError as e:
            if e.sequence_name == "test_sequence":
                print(f"  PASSED: SequenceFetchError raised with sequence_name='{e.sequence_name}'")
                return True
            else:
                print(f"  FAILED: Wrong sequence_name: {e.sequence_name}")
                return False
        except Exception as e:
            print(f"  FAILED: Wrong exception type: {type(e).__name__}: {e}")
            return False

def test_retry_failed_error():
    """Test next_sequence_values raises SequenceRetryFailedError after a failed retry."""
    print("Testing SequenceRetryFailedError...")
    with DuckDBStorageManager() as storage:
        storage.ensure_sequence("test_sequence")

        # Mock _is_invalidated_error to return True
        storage._is_invalidated_error = MagicMock(return_value=True)

        # Mock execute to always raise duckdb.Error
        storage.execute = MagicMock(side_effect=duckdb.Error("DB error"))

        try:
            storage.next_sequence_values("test_sequence")
            print("  FAILED: No exception raised")
            return False
        except SequenceRetryFailedError as e:
            if e.sequence_name == "test_sequence":
                print(f"  PASSED: SequenceRetryFailedError raised with sequence_name='{e.sequence_name}'")
                return True
            else:
                print(f"  FAILED: Wrong sequence_name: {e.sequence_name}")
                return False
        except Exception as e:
            print(f"  FAILED: Wrong exception type: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    results = []
    results.append(test_fetch_error())
    print()
    results.append(test_retry_failed_error())
    print()

    if all(results):
        print("All tests PASSED!")
        sys.exit(0)
    else:
        print("Some tests FAILED!")
        sys.exit(1)
