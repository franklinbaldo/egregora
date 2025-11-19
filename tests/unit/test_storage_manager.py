"""Tests for DuckDBStorageManager (Priority C.2)."""

from pathlib import Path

import duckdb
import ibis
import pytest
from ibis.expr.types import Table

from egregora.database.duckdb_manager import (
    DuckDBNoOpVectorBackend,
    DuckDBStorageManager,
    DuckDBVectorBackend,
    temp_storage,
)


class TestStorageManagerInit:
    """Tests for DuckDBStorageManager initialization."""

    def test_init_in_memory(self):
        """Test initialization with in-memory database."""
        storage = DuckDBStorageManager()
        assert storage.db_path is None
        assert storage.conn is not None
        assert storage.ibis_conn is not None
        storage.close()

    def test_init_with_file(self, tmp_path):
        """Test initialization with file-based database."""
        db_path = tmp_path / "test.duckdb"
        storage = DuckDBStorageManager(db_path=db_path)

        assert storage.db_path == db_path
        assert storage.conn is not None
        storage.close()

        # Verify file was created
        assert db_path.exists()

    def test_init_custom_checkpoint_dir(self, tmp_path):
        """Test initialization with custom checkpoint directory."""
        checkpoint_dir = tmp_path / "checkpoints"
        storage = DuckDBStorageManager(checkpoint_dir=checkpoint_dir)

        assert storage.checkpoint_dir == checkpoint_dir
        storage.close()

    def test_context_manager(self):
        """Test DuckDBStorageManager as context manager."""
        with DuckDBStorageManager() as storage:
            assert storage.conn is not None

        # Connection should be closed after exit
        with pytest.raises(duckdb.ConnectionException):  # type: ignore[attr-defined]
            storage.conn.execute("SELECT 1")


class TestTableOperations:
    """Tests for table read/write operations."""

    def test_write_and_read_table(self):
        """Test writing and reading a table."""
        with DuckDBStorageManager() as storage:
            # Create sample table
            data = {"id": [1, 2, 3], "value": ["a", "b", "c"]}
            schema = {"id": "int64", "value": "string"}
            table = ibis.memtable(data, schema=schema)

            # Write table
            storage.write_table(table, "test_table", checkpoint=False)

            # Read table back
            result = storage.read_table("test_table")
            df = result.execute()

            # Verify data
            assert len(df) == 3
            assert list(df["id"]) == [1, 2, 3]
            assert list(df["value"]) == ["a", "b", "c"]

    def test_write_with_checkpoint(self, tmp_path):
        """Test writing table with parquet checkpoint."""
        checkpoint_dir = tmp_path / "checkpoints"
        with DuckDBStorageManager(checkpoint_dir=checkpoint_dir) as storage:
            # Create sample table
            data = {"id": [1, 2, 3]}
            schema = {"id": "int64"}
            table = ibis.memtable(data, schema=schema)

            # Write with checkpoint
            storage.write_table(table, "checkpointed_table", checkpoint=True)

            # Verify checkpoint file exists
            checkpoint_path = checkpoint_dir / "checkpointed_table.parquet"
            assert checkpoint_path.exists()

            # Verify data can be read
            result = storage.read_table("checkpointed_table")
            df = result.execute()
            assert len(df) == 3

    def test_write_mode_replace(self):
        """Test replace mode overwrites existing table."""
        with DuckDBStorageManager() as storage:
            # Write initial data
            table1 = ibis.memtable({"id": [1, 2]}, schema={"id": "int64"})
            storage.write_table(table1, "test_replace", checkpoint=False)

            # Replace with new data
            table2 = ibis.memtable({"id": [3, 4, 5]}, schema={"id": "int64"})
            storage.write_table(table2, "test_replace", mode="replace", checkpoint=False)

            # Verify only new data exists
            result = storage.read_table("test_replace")
            df = result.execute()
            assert len(df) == 3
            assert list(df["id"]) == [3, 4, 5]

    def test_write_mode_append_requires_checkpoint(self):
        """Test append mode requires checkpoint=True."""
        with DuckDBStorageManager() as storage:
            table = ibis.memtable({"id": [1]}, schema={"id": "int64"})

            with pytest.raises(ValueError, match="Append mode requires checkpoint"):
                storage.write_table(table, "test", mode="append", checkpoint=False)

    def test_read_nonexistent_table_raises(self):
        """Test reading non-existent table raises ValueError."""
        with DuckDBStorageManager() as storage:
            with pytest.raises(ValueError, match="Table 'nonexistent' not found"):
                storage.read_table("nonexistent")


class TestTableManagement:
    """Tests for table management operations."""

    def test_table_exists(self):
        """Test checking if table exists."""
        with DuckDBStorageManager() as storage:
            assert not storage.table_exists("test_table")

            # Create table
            table = ibis.memtable({"id": [1]}, schema={"id": "int64"})
            storage.write_table(table, "test_table", checkpoint=False)

            assert storage.table_exists("test_table")

    def test_list_tables(self):
        """Test listing all tables."""
        with DuckDBStorageManager() as storage:
            # Initially empty
            assert storage.list_tables() == []

            # Create tables
            table = ibis.memtable({"id": [1]}, schema={"id": "int64"})
            storage.write_table(table, "table_a", checkpoint=False)
            storage.write_table(table, "table_b", checkpoint=False)

            # List should be sorted
            tables = storage.list_tables()
            assert tables == ["table_a", "table_b"]

    def test_drop_table(self):
        """Test dropping a table."""
        with DuckDBStorageManager() as storage:
            # Create table
            table = ibis.memtable({"id": [1]}, schema={"id": "int64"})
            storage.write_table(table, "drop_me", checkpoint=False)

            assert storage.table_exists("drop_me")

            # Drop table
            storage.drop_table("drop_me")

            assert not storage.table_exists("drop_me")

    def test_drop_table_with_checkpoint(self, tmp_path):
        """Test dropping table and checkpoint together."""
        checkpoint_dir = tmp_path / "checkpoints"
        with DuckDBStorageManager(checkpoint_dir=checkpoint_dir) as storage:
            # Create table with checkpoint
            table = ibis.memtable({"id": [1]}, schema={"id": "int64"})
            storage.write_table(table, "drop_me", checkpoint=True)

            checkpoint_path = checkpoint_dir / "drop_me.parquet"
            assert checkpoint_path.exists()

            # Drop both table and checkpoint
            storage.drop_table("drop_me", checkpoint_too=True)

            assert not storage.table_exists("drop_me")
            assert not checkpoint_path.exists()

    def test_drop_nonexistent_table_safe(self):
        """Test dropping non-existent table doesn't raise."""
        with DuckDBStorageManager() as storage:
            # Should not raise
            storage.drop_table("nonexistent")


class TestViewExecution:
    """Tests for executing view builder callables."""

    def test_execute_view_basic(self):
        """Test executing a simple view transformation."""
        with DuckDBStorageManager() as storage:
            # Create input table
            table = ibis.memtable(
                {"id": [1, 2, 3, 4, 5]},
                schema={"id": "int64"},
            )
            storage.write_table(table, "input", checkpoint=False)

            # Define view builder
            def limit_3(ir: Table) -> Table:
                return ir.limit(3)

            # Execute view
            result = storage.execute_view("output", limit_3, "input", checkpoint=False)

            # Verify result
            df = result.execute()
            assert len(df) == 3

    def test_execute_view_with_checkpoint(self, tmp_path):
        """Test executing view with checkpoint."""
        checkpoint_dir = tmp_path / "checkpoints"
        with DuckDBStorageManager(checkpoint_dir=checkpoint_dir) as storage:
            # Create input table
            table = ibis.memtable(
                {"value": [1, 2, 3]},
                schema={"value": "int64"},
            )
            storage.write_table(table, "input", checkpoint=False)

            # Define view builder
            def double_values(ir: Table) -> Table:
                return ir.mutate(doubled=ir.value * 2)

            # Execute view with checkpoint
            result = storage.execute_view(
                "doubled",
                double_values,
                "input",
                checkpoint=True,
            )

            # Verify checkpoint created
            checkpoint_path = checkpoint_dir / "doubled.parquet"
            assert checkpoint_path.exists()

            # Verify table created
            assert storage.table_exists("doubled")

            # Verify data
            df = result.execute()
            assert "doubled" in df.columns

    def test_execute_view_with_common_view(self):
        """Test executing a built-in common view."""
        from egregora.database.views import messages_with_media_view

        with DuckDBStorageManager() as storage:
            # Create input table matching ViewRegistry expectations
            import uuid
            from datetime import datetime

            data = {
                "event_id": [str(uuid.uuid4()), str(uuid.uuid4())],
                "thread_id": [str(uuid.uuid4()), str(uuid.uuid4())],
                "ts": [datetime(2025, 1, 1, 10, 0), datetime(2025, 1, 1, 11, 0)],
                "text": ["msg1", "msg2"],
                "media_url": ["http://example.com/img.jpg", None],
            }
            schema = {
                "event_id": "uuid",
                "thread_id": "uuid",
                "ts": "timestamp",
                "text": "string",
                "media_url": "string",
            }
            table = ibis.memtable(data, schema=schema)
            storage.write_table(table, "conversations", checkpoint=False)

            # Execute built-in view
            media_filter = messages_with_media_view
            result = storage.execute_view(
                "media_messages",
                media_filter,
                "conversations",
                checkpoint=False,
            )

            # Verify filtering worked
            df = result.execute()
            assert len(df) == 1  # Only one message has media_url


class TestTempStorage:
    """Tests for temp_storage convenience function."""

    def test_temp_storage(self):
        """Test creating temporary storage."""
        with temp_storage() as storage:
            assert storage.db_path is None
            assert storage.checkpoint_dir == Path("/tmp/.egregora-temp")

            # Should work like normal storage
            table = ibis.memtable({"id": [1]}, schema={"id": "int64"})
            storage.write_table(table, "temp_table", checkpoint=False)
            assert storage.table_exists("temp_table")


class TestCheckpointPersistence:
    """Tests for checkpoint persistence across sessions."""

    def test_checkpoint_persists_across_connections(self, tmp_path):
        """Test that checkpoints can be loaded in new connection."""
        db_path = tmp_path / "test.duckdb"
        checkpoint_dir = tmp_path / "checkpoints"

        # Session 1: Write data
        with DuckDBStorageManager(db_path=db_path, checkpoint_dir=checkpoint_dir) as storage1:
            table = ibis.memtable(
                {"id": [1, 2, 3], "name": ["alice", "bob", "charlie"]},
                schema={"id": "int64", "name": "string"},
            )
            storage1.write_table(table, "users", checkpoint=True)

        # Session 2: Read data
        with DuckDBStorageManager(db_path=db_path, checkpoint_dir=checkpoint_dir) as storage2:
            result = storage2.read_table("users")
            df = result.execute()

            assert len(df) == 3
            assert list(df["name"]) == ["alice", "bob", "charlie"]


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_table(self):
        """Test handling empty tables."""
        with DuckDBStorageManager() as storage:
            # Create empty table
            empty_table = ibis.memtable([], schema={"id": "int64"})
            storage.write_table(empty_table, "empty", checkpoint=False)

            # Read back
            result = storage.read_table("empty")
            df = result.execute()
            assert len(df) == 0

    def test_large_table_names(self):
        """Test handling long table names."""
        with DuckDBStorageManager() as storage:
            long_name = "table_" + "x" * 100
            table = ibis.memtable({"id": [1]}, schema={"id": "int64"})
            storage.write_table(table, long_name, checkpoint=False)

            assert storage.table_exists(long_name)

    def test_special_characters_in_data(self):
        """Test handling special characters in string data."""
        with DuckDBStorageManager() as storage:
            data = {"text": ["hello", "world's", 'quote"test', "line\nbreak"]}
            schema = {"text": "string"}
            table = ibis.memtable(data, schema=schema)

            storage.write_table(table, "special_chars", checkpoint=False)

            result = storage.read_table("special_chars")
            df = result.execute()
            assert len(df) == 4


class TestSequenceHelpers:
    def test_sequence_creation_and_next_value(self):
        with DuckDBStorageManager() as storage:
            storage.ensure_sequence("test_seq")
            first = storage.next_sequence_value("test_seq")
            second = storage.next_sequence_value("test_seq")

            assert second == first + 1

    def test_sequence_default_and_sync(self):
        with DuckDBStorageManager() as storage:
            storage.ensure_sequence("table_seq")
            storage.conn.execute(
                """
                CREATE TABLE records (
                    id INTEGER,
                    name VARCHAR
                )
                """
            )
            storage.ensure_sequence_default("records", "id", "table_seq")

            storage.conn.execute("INSERT INTO records (id, name) VALUES (10, 'alpha')")
            storage.sync_sequence_with_table("table_seq", table="records", column="id")

            assert storage.next_sequence_value("table_seq") >= 11

    def test_next_sequence_values_batch(self):
        with DuckDBStorageManager() as storage:
            storage.ensure_sequence("batch_seq")
            values = storage.next_sequence_values("batch_seq", count=3)

            assert values == [1, 2, 3]


class TestVectorBackendFactory:
    """Ensure DuckDBStorageManager exposes vector backends."""

    def test_create_vector_backend_defaults_to_duckdb_impl(self):
        with DuckDBStorageManager() as storage:
            backend = storage.create_vector_backend()
            assert isinstance(backend, DuckDBVectorBackend)
            # Should be able to safely drop non-existent tables
            backend.drop_table("nonexistent_chunks")

    def test_create_vector_backend_noop(self):
        with DuckDBStorageManager() as storage:
            backend = storage.create_vector_backend(enable_vss=False)
            assert isinstance(backend, DuckDBNoOpVectorBackend)
            assert backend.install_extensions() is False

    def test_vector_backend_materializes_table(self, tmp_path):
        db_path = tmp_path / "backend.duckdb"
        parquet_path = tmp_path / "chunks.parquet"
        with DuckDBStorageManager(db_path=db_path) as storage:
            backend = storage.create_vector_backend(enable_vss=False)
            storage.conn.execute(
                "COPY (SELECT 'chunk-1' AS chunk_id) TO ? (FORMAT PARQUET)",
                [str(parquet_path)],
            )
            backend.materialize_chunks_table("rag_chunks_test", parquet_path)
            assert backend.table_exists("rag_chunks_test")
            assert backend.row_count("rag_chunks_test") == 1
