"""Behavioral tests for DuckDBStorageManager.

These tests verify the actual integration with DuckDB and the filesystem,
complementing the mock-based unit tests in test_duckdb_manager.py.
"""

import shutil

import ibis
import pytest

from egregora.database.duckdb_manager import temp_storage
from egregora.database.exceptions import TableNotFoundError


@pytest.fixture
def storage():
    """Provide a temporary storage manager."""
    mgr = temp_storage()
    yield mgr
    mgr.close()
    if mgr.checkpoint_dir and mgr.checkpoint_dir.exists():
        shutil.rmtree(mgr.checkpoint_dir)


def test_table_lifecycle(storage):
    """Verify basic table CRUD operations."""
    data = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}, {"a": 3, "b": "z"}]
    t = ibis.memtable(data)

    # Write
    storage.write_table(t, "test_table", checkpoint=False)
    assert storage.table_exists("test_table")
    assert "test_table" in storage.list_tables()

    # Read
    t_read = storage.read_table("test_table")
    res_read = t_read.execute().to_dict(orient="records")
    # Sort to compare
    res_read.sort(key=lambda x: x["a"])
    assert res_read == data

    # Drop
    storage.drop_table("test_table")
    assert not storage.table_exists("test_table")
    assert "test_table" not in storage.list_tables()

    # Read missing
    with pytest.raises(TableNotFoundError):
        storage.read_table("test_table")


def test_checkpointing(storage):
    """Verify parquet checkpoints are created and removed."""
    data = [{"id": 1, "val": 10}]
    t = ibis.memtable(data)
    table_name = "checkpoint_test"

    # Write with checkpoint
    storage.write_table(t, table_name, checkpoint=True)

    # Verify file exists
    expected_path = storage.checkpoint_dir / f"{table_name}.parquet"
    assert expected_path.exists()
    assert expected_path.stat().st_size > 0

    # Drop with checkpoint
    storage.drop_table(table_name, checkpoint_too=True)
    assert not expected_path.exists()


def test_append_mode(storage):
    """Verify append mode works with checkpoints."""
    data1 = [{"id": 1, "val": "a"}]
    data2 = [{"id": 2, "val": "b"}]

    t1 = ibis.memtable(data1)
    t2 = ibis.memtable(data2)
    table_name = "append_test"

    # Initial write (replace)
    storage.write_table(t1, table_name, checkpoint=True)
    assert storage.row_count(table_name) == 1

    # Append
    storage.write_table(t2, table_name, mode="append", checkpoint=True)
    assert storage.row_count(table_name) == 2

    # Verify data
    result = storage.read_table(table_name).order_by("id").execute().to_dict(orient="records")
    assert result == [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]


def test_sequences(storage):
    """Verify sequence creation, increment, and state."""
    seq_name = "behavioral_seq"

    # Create
    storage.ensure_sequence(seq_name, start=10)
    state = storage.get_sequence_state(seq_name)
    assert state.start_value == 10

    # Next value
    val = storage.next_sequence_value(seq_name)
    assert val == 10  # First value is start value

    # Next values batch
    vals = storage.next_sequence_values(seq_name, count=3)
    assert vals == [11, 12, 13]

    # Verify state
    state = storage.get_sequence_state(seq_name)
    assert state.last_value == 13


def test_sync_sequence_with_table(storage):
    """Verify sequence syncs to table max value."""
    table_name = "sync_test"
    seq_name = "sync_seq"
    col_name = "id"

    # Create table with data
    data = [{col_name: 100}, {col_name: 200}, {col_name: 500}]
    t = ibis.memtable(data)
    storage.write_table(t, table_name, checkpoint=False)

    # Create sequence at 1
    storage.ensure_sequence(seq_name, start=1)
    assert storage.next_sequence_value(seq_name) == 1

    # Sync
    storage.sync_sequence_with_table(seq_name, table=table_name, column=col_name)

    # Next value should be > 500
    val = storage.next_sequence_value(seq_name)
    assert val == 501


def test_persist_atomic(storage):
    """Verify atomic persistence preserves schema and updates data."""
    table_name = "atomic_test"

    # Define schema
    schema = ibis.schema({"id": "int64", "data": "string"})

    # Initial data
    data1 = [{"id": 1, "data": "old"}]
    t1 = ibis.memtable(data1, schema=schema)

    # Use write_table to simulate initial state (though persist_atomic works on empty too)
    storage.write_table(t1, table_name, checkpoint=True)

    # New data with compatible schema
    data2 = [{"id": 2, "data": "new"}]
    t2 = ibis.memtable(data2, schema=schema)

    # Persist atomic
    storage.persist_atomic(t2, table_name, schema=schema)

    # Verify
    result = storage.read_table(table_name).execute().to_dict(orient="records")
    assert len(result) == 1
    assert result[0]["id"] == 2
    assert result[0]["data"] == "new"


def test_persist_atomic_creates_table(storage):
    """Verify persist_atomic creates table if it doesn't exist."""
    table_name = "atomic_create_test"
    schema = ibis.schema({"id": "int64", "data": "string"})

    data = [{"id": 1, "data": "init"}]
    t = ibis.memtable(data, schema=schema)

    storage.persist_atomic(t, table_name, schema=schema)

    assert storage.table_exists(table_name)
    assert storage.row_count(table_name) == 1


def test_replace_rows(storage):
    """Verify replace_rows simulates UPSERT."""
    table_name = "upsert_test"

    # Initial data
    data = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
    t = ibis.memtable(data)
    storage.write_table(t, table_name, checkpoint=True)

    # New data to replace id=1
    data_new = [{"id": 1, "val": "updated"}]
    t_new = ibis.memtable(data_new)

    # Execute replace
    storage.replace_rows(table_name, t_new, by_keys={"id": 1})

    # Verify: id=1 should be updated, id=2 should remain
    result = storage.read_table(table_name).order_by("id").execute().to_dict(orient="records")
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[0]["val"] == "updated"
    assert result[1]["id"] == 2
    assert result[1]["val"] == "b"
