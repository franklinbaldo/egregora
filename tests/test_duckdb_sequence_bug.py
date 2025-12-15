"""Test to reproduce DuckDB read-only transaction bug.

Bug: "Attempting to commit a transaction that is read-only but has made changes"
Location: duckdb_manager.py:585 in next_sequence_values()
"""

import contextlib
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from egregora.database.duckdb_manager import DuckDBStorageManager


def test_sequence_values_single_thread():
    """Test sequence generation in single thread (should work)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        manager = DuckDBStorageManager(db_path)

        # Create a sequence
        manager.execute("CREATE SEQUENCE IF NOT EXISTS test_seq START 1")

        # Get multiple batches of sequence values
        for _ in range(10):
            values = manager.next_sequence_values("test_seq", count=5)
            assert len(values) == 5
            assert all(isinstance(v, int) for v in values)

        manager.close()


def test_sequence_values_concurrent_threads():
    """Test sequence generation with concurrent threads (may reproduce bug).

    This test attempts to reproduce the error:
    "Attempting to commit a transaction that is read-only but has made changes"

    The bug occurs when multiple threads try to use next_sequence_values()
    simultaneously, possibly due to transaction state issues.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        manager = DuckDBStorageManager(db_path)

        # Create a sequence
        manager.execute("CREATE SEQUENCE IF NOT EXISTS test_seq START 1")

        def get_sequence_batch(thread_id: int) -> list[int]:
            """Get a batch of sequence values in a thread."""
            try:
                return manager.next_sequence_values("test_seq", count=10)
            except Exception:
                raise

        # Run concurrent sequence requests
        errors = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_sequence_batch, i) for i in range(20)]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    assert len(result) == 10
                except Exception as e:
                    errors.append(e)

        manager.close()

        # If we got the specific error, the bug is reproduced
        readonly_errors = [
            e for e in errors if "read-only" in str(e).lower() and "transaction" in str(e).lower()
        ]

        if readonly_errors:
            pytest.fail(
                f"Reproduced DuckDB bug! Got {len(readonly_errors)} read-only "
                f"transaction errors out of 20 threads. "
                f"First error: {readonly_errors[0]}"
            )


def test_sequence_values_with_explicit_transactions():
    """Test sequence generation with explicit transaction management.

    Tests whether explicitly managing transactions helps avoid the bug.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        manager = DuckDBStorageManager(db_path)

        # Create a sequence
        manager.execute("CREATE SEQUENCE IF NOT EXISTS test_seq START 1")

        # Get sequence values with explicit transaction control
        for i in range(10):
            # Try to ensure we're in correct transaction state
            try:
                manager._conn.begin()
                values = manager.next_sequence_values("test_seq", count=5)
                manager._conn.commit()
                assert len(values) == 5
            except Exception as e:
                manager._conn.rollback()
                pytest.fail(f"Iteration {i}: Transaction error: {e}")

        manager.close()


def test_sequence_values_rapid_fire():
    """Test rapid-fire sequence requests (stress test).

    Attempts to trigger the bug through rapid consecutive requests.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        manager = DuckDBStorageManager(db_path)

        # Create a sequence
        manager.execute("CREATE SEQUENCE IF NOT EXISTS test_seq START 1")

        errors = []

        # Rapid-fire requests
        for i in range(100):
            try:
                values = manager.next_sequence_values("test_seq", count=1)
                assert len(values) == 1
            except Exception as e:
                errors.append((i, e))

        manager.close()

        if errors:
            readonly_errors = [(i, e) for i, e in errors if "read-only" in str(e).lower()]
            if readonly_errors:
                pytest.fail(
                    f"Bug reproduced in rapid-fire test! "
                    f"Got {len(readonly_errors)} errors. "
                    f"First at iteration {readonly_errors[0][0]}: "
                    f"{readonly_errors[0][1]}"
                )


def test_sequence_after_connection_reset():
    """Test sequence generation after connection reset.

    The bug involves connection invalidation - test if reset helps.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        manager = DuckDBStorageManager(db_path)

        # Create a sequence
        manager.execute("CREATE SEQUENCE IF NOT EXISTS test_seq START 1")

        # Get some values
        values1 = manager.next_sequence_values("test_seq", count=5)
        assert len(values1) == 5

        # Simulate connection reset (like in the error recovery code)
        manager._reset_connection()

        # Try to get more values after reset
        values2 = manager.next_sequence_values("test_seq", count=5)
        assert len(values2) == 5

        # Values should continue from where we left off
        assert values2[0] > values1[-1]

        manager.close()


if __name__ == "__main__":
    # Run tests standalone for debugging
    test_sequence_values_single_thread()

    with contextlib.suppress(Exception):
        test_sequence_values_concurrent_threads()

    test_sequence_values_with_explicit_transactions()

    with contextlib.suppress(Exception):
        test_sequence_values_rapid_fire()

    test_sequence_after_connection_reset()
