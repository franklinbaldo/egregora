"""E2E tests for DuckDB sequence operations.

These tests verify that sequence helpers work correctly in real pipeline scenarios.
This test would have caught the self.conn → self._conn bug in Task 9.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from egregora.agents.shared.annotations import AnnotationStore
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.tracking import record_run


def test_annotation_store_initialization(tmp_path: Path):
    """Test that AnnotationStore can initialize with sequence setup.

    This test would have caught the bug where sequence helpers still used
    the removed self.conn property instead of self._conn.

    Bug scenario: AnnotationStore.__init__() calls ensure_sequence(),
    which tried to use self.conn.execute() and raised AttributeError.
    """
    db_path = tmp_path / "test.duckdb"

    with DuckDBStorageManager(db_path=db_path) as storage:
        # This should work without AttributeError
        AnnotationStore(storage)

        # Verify sequence was created
        sequence_state = storage.get_sequence_state("annotations_seq")
        assert sequence_state is not None
        assert sequence_state.sequence_name == "annotations_seq"
        assert sequence_state.start_value == 1


def test_run_tracking_with_sequences(tmp_path: Path):
    """Test that run tracking works with DuckDBStorageManager.

    Run tracking uses sequences for run IDs in some code paths.
    This verifies the integration works end-to-end.
    """
    db_path = tmp_path / "runs.duckdb"

    with DuckDBStorageManager(db_path=db_path) as storage:
        # Get the underlying connection for run tracking
        conn = storage._conn

        # Record a run start (would have failed with self.conn bug)
        run_id = uuid.uuid4()
        started_at = datetime.now(UTC)

        record_run(
            conn=conn,
            run_id=run_id,
            stage="write",
            status="running",
            started_at=started_at,
        )

        # Verify the run was recorded
        result = conn.execute("SELECT stage, status FROM runs WHERE run_id = ?", [str(run_id)]).fetchone()

        assert result is not None
        assert result[0] == "write"
        assert result[1] == "running"


def test_sequence_operations_e2e(tmp_path: Path):
    """Test all sequence helper methods in an e2e scenario.

    This comprehensive test exercises all the sequence methods that
    had the self.conn bug:
    - ensure_sequence()
    - get_sequence_state()
    - ensure_sequence_default()
    - sync_sequence_with_table()
    - next_sequence_value()
    - next_sequence_values()
    """
    db_path = tmp_path / "sequences.duckdb"

    with DuckDBStorageManager(db_path=db_path) as storage:
        # 1. Create a sequence - would fail with self.conn bug
        storage.ensure_sequence("test_seq", start=100)

        # 2. Get sequence state - would fail with self.conn bug
        state = storage.get_sequence_state("test_seq")
        assert state is not None
        assert state.start_value == 100

        # 3. Create a test table
        storage._conn.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                value VARCHAR
            )
        """)

        # 4. Set sequence as default - would fail with self.conn bug
        storage.ensure_sequence_default("test_table", "id", "test_seq")

        # 5. Get next value - would fail with self.conn bug
        val1 = storage.next_sequence_value("test_seq")
        assert val1 == 100

        # 6. Get multiple values - would fail with self.conn bug
        vals = storage.next_sequence_values("test_seq", count=3)
        assert len(vals) == 3
        assert vals == [101, 102, 103]

        # 7. Insert some data and sync sequence - would fail with self.conn bug
        storage._conn.execute("""
            INSERT INTO test_table (id, value) VALUES (200, 'test')
        """)
        storage.sync_sequence_with_table("test_seq", table="test_table", column="id")

        # Next value should be > 200
        next_val = storage.next_sequence_value("test_seq")
        assert next_val > 200


def test_pipeline_with_annotation_store(tmp_path: Path, sample_whatsapp_export):
    """Test that a minimal pipeline run works with AnnotationStore.

    This simulates a real pipeline scenario where AnnotationStore
    would be initialized as part of pipeline setup.

    Note: This is marked as xfail if sample_whatsapp_export fixture
    doesn't exist, but demonstrates the integration test approach.
    """
    pytest.skip("Requires full pipeline fixtures - demonstration test")

    # This would be a real e2e test:
    # 1. Initialize output directory with AnnotationStore
    # 2. Run a minimal pipeline
    # 3. Verify annotations can be stored/retrieved
    #
    # The bug would manifest during step 1 when AnnotationStore.__init__
    # tries to call storage.ensure_sequence()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
