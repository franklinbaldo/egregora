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

        # Verify sequence was created (AnnotationStore uses 'annotations_id_seq')
        sequence_state = storage.get_sequence_state("annotations_id_seq")
        assert sequence_state is not None
        assert sequence_state.sequence_name == "annotations_id_seq"
        assert sequence_state.start_value == 1


from egregora.database.tracking import RunMetadata, record_run


def test_run_tracking_with_sequences(tmp_path: Path):
    """Test that run tracking works with DuckDBStorageManager."""
    db_path = tmp_path / "runs.duckdb"

    with DuckDBStorageManager(db_path=db_path) as storage:
        run_id = uuid.uuid4()
        started_at = datetime.now(UTC)

        metadata = RunMetadata(
            run_id=run_id,
            stage="write",
            status="running",
            started_at=started_at,
        )
        record_run(conn=storage, metadata=metadata)

        result = storage._conn.execute(
            "SELECT stage, status FROM runs WHERE run_id = ?", [str(run_id)]
        ).fetchone()

        assert result is not None
        assert result[0] == "write"
        assert result[1] == "running"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
