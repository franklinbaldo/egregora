"""Tests for the RunStore facade that now relies on DuckDBStorageManager."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import uuid

import pytest

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.run_store import RunStore
from egregora.database.tracking import record_run


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "run_store.duckdb"


@pytest.fixture
def storage(temp_db_path: Path) -> DuckDBStorageManager:
    return DuckDBStorageManager(db_path=temp_db_path)


def test_run_store_latest_runs(storage: DuckDBStorageManager) -> None:
    """RunStore.get_latest_runs() returns newest rows via manager helpers."""

    base = datetime.now(UTC) - timedelta(minutes=5)
    for idx in range(3):
        started_at = base + timedelta(minutes=idx)
        record_run(
            conn=storage,
            run_id=uuid.uuid4(),
            stage=f"stage-{idx}",
            status="completed",
            started_at=started_at,
            finished_at=started_at,
            rows_in=idx,
            rows_out=idx,
        )

    store = RunStore(storage)
    rows = store.get_latest_runs(2)

    assert len(rows) == 2
    assert rows[0][3] >= rows[1][3]  # started_at is descending


def test_run_store_get_run_by_id(storage: DuckDBStorageManager) -> None:
    """RunStore.get_run_by_id() can look up rows using partial IDs."""

    run_id = uuid.uuid4()
    record_run(
        conn=storage,
        run_id=run_id,
        stage="lookup-stage",
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        rows_in=10,
        rows_out=5,
    )

    store = RunStore(storage)
    row = store.get_run_by_id(str(run_id)[:8])

    assert row is not None
    assert row[0] == run_id
    assert row[2] == "lookup-stage"
