from unittest.mock import MagicMock, patch

import duckdb
import ibis
from egregora.database.duckdb_manager import DuckDBStorageManager, temp_storage


def test_execute_wrappers_behavior():
    """Verify execute wrappers behave as expected with a real DB."""
    with temp_storage() as storage:
        # execute_sql
        storage.execute_sql("CREATE TABLE test (id INTEGER, name VARCHAR)")
        storage.execute_sql("INSERT INTO test VALUES (1, 'Alice'), (2, 'Bob')")

        # execute_query
        rows = storage.execute_query("SELECT * FROM test ORDER BY id")
        assert len(rows) == 2
        assert rows[0] == (1, "Alice")
        assert rows[1] == (2, "Bob")

        # execute_query_single
        row = storage.execute_query_single("SELECT name FROM test WHERE id = ?", [1])
        assert row == ("Alice",)

        # execute
        relation = storage.execute("SELECT count(*) FROM test")
        assert relation.fetchone()[0] == 2


def test_write_table_append_checkpoint_behavior(tmp_path):
    """Verify write_table in append mode with checkpointing."""
    db_path = tmp_path / "test.duckdb"
    checkpoint_dir = tmp_path / "checkpoints"

    with DuckDBStorageManager(db_path=db_path, checkpoint_dir=checkpoint_dir) as storage:
        # Create initial data
        t1 = ibis.memtable({"id": [1], "val": ["a"]})

        # Write first batch (replace)
        storage.write_table(t1, "data", mode="replace", checkpoint=True)

        # Verify checkpoint exists
        parquet_path = checkpoint_dir / "data.parquet"
        assert parquet_path.exists()

        # Verify data in DB
        assert storage.row_count("data") == 1

        # Create second batch
        t2 = ibis.memtable({"id": [2], "val": ["b"]})

        # Write second batch (append)
        storage.write_table(t2, "data", mode="append", checkpoint=True)

        # Verify data in DB
        rows = storage.execute_query("SELECT id, val FROM data ORDER BY id")
        assert len(rows) == 2
        assert rows[0] == (1, "a")
        assert rows[1] == (2, "b")

        # Verify parquet was updated (last write content)
        # We use duckdb directly to verify parquet content without pandas
        res = duckdb.query(f"SELECT * FROM '{parquet_path}'").fetchall()
        assert len(res) == 1
        # DuckDB returns tuples in column order.
        # Note: Ibis memtable dict order might not be preserved, but keys are usually stable enough here.
        # Or we check by value.
        assert res[0] == (2, "b") or res[0] == ("b", 2)


def test_sequence_batch_behavior():
    """Verify next_sequence_values for counts > 1."""
    with temp_storage() as storage:
        storage.ensure_sequence("seq_test", start=10)

        values = storage.next_sequence_values("seq_test", count=5)
        assert values == [10, 11, 12, 13, 14]

        val = storage.next_sequence_value("seq_test")
        assert val == 15


def test_sequence_sync_behavior():
    """Verify sync_sequence_with_table behavior."""
    with temp_storage() as storage:
        storage.execute_sql("CREATE TABLE items (id INTEGER)")
        storage.execute_sql("INSERT INTO items VALUES (1), (50)")

        storage.ensure_sequence("item_seq", start=1)

        # Should jump to 51
        storage.sync_sequence_with_table("item_seq", table="items", column="id")

        next_val = storage.next_sequence_value("item_seq")
        assert next_val == 51


@patch("ibis.duckdb.connect")
@patch("pathlib.Path.unlink")
def test_reset_connection_successful_recovery(mock_unlink, mock_connect):
    """Test the path where invalidation occurs, file is unlinked, and reconnection succeeds."""
    # 1. Initial success
    # 2. Reconnect fails with invalidation
    # 3. Reconnect succeeds (after unlink)

    conn_mock = MagicMock()
    conn_mock.execute.return_value.fetchall.return_value = []  # For pragma database_list or others

    mock_connect.side_effect = [
        MagicMock(),  # __init__
        duckdb.Error("database has been invalidated"),  # First _connect in _reset_connection
        MagicMock(),  # Second _connect after unlink
    ]

    storage = DuckDBStorageManager(db_path="test.db")
    # Mock internal lock to avoid thread issues if any (though mocks usually bypass)
    storage._lock = MagicMock()
    storage._conn = MagicMock()  # The one being closed

    # Use real logic for _is_invalidated_error since we want to test that method too if possible,
    # but we are mocking the exception source.
    # The method checks str(exc).

    storage._reset_connection()

    # Verify unlink was called
    mock_unlink.assert_called_once()

    # Verify connect was called 3 times (init, fail, success)
    assert mock_connect.call_count == 3

    # Verify we didn't fall back to memory
    assert storage.db_path is not None


def test_persist_atomic_behavior():
    """Verify persist_atomic success path."""
    with temp_storage() as storage:
        # Create initial schema
        storage.execute_sql("CREATE TABLE atomic_test (id INTEGER, val VARCHAR)")
        storage.execute_sql("INSERT INTO atomic_test VALUES (1, 'old')")

        # New data
        t = ibis.memtable({"id": [1, 2], "val": ["new", "newer"]})

        # Persist atomic
        # Note: Ibis schemas might need explicit definition if inferred
        schema = ibis.schema({"id": "int64", "val": "string"})

        storage.persist_atomic(t, "atomic_test", schema=schema)

        # Verify result
        rows = storage.execute_query("SELECT * FROM atomic_test ORDER BY id")
        assert len(rows) == 2
        assert rows[0] == (1, "new")
        assert rows[1] == (2, "newer")


def test_write_table_no_checkpoint():
    """Verify write_table without checkpoint (memory only)."""
    with temp_storage() as storage:
        t = ibis.memtable({"id": [99], "val": ["mem"]})

        storage.write_table(t, "mem_table", mode="replace", checkpoint=False)

        assert storage.table_exists("mem_table")
        assert storage.row_count("mem_table") == 1

        # Verify NO checkpoint
        assert not (storage.checkpoint_dir / "mem_table.parquet").exists()
