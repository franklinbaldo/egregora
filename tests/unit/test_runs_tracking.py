"""Unit tests for pipeline run tracking and lineage.

Tests:
- RunContext creation
- record_run() writes to runs table
- record_lineage() writes to lineage table
- run_stage_with_tracking() wrapper
- Fingerprinting for checkpointing
- Error handling and failure recording
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import ibis
import pytest

from egregora.pipeline.runner import (
    RunContext,
    fingerprint_table,
    get_git_commit_sha,
    record_lineage,
    record_run,
    run_stage_with_tracking,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create temporary DuckDB database path."""
    return tmp_path / "test_runs.duckdb"


@pytest.fixture
def runs_db(temp_db_path: Path) -> duckdb.DuckDBPyConnection:
    """Create DuckDB with runs and lineage tables."""
    conn = duckdb.connect(str(temp_db_path))

    # Create runs table (simplified schema for testing)
    conn.execute("""
        CREATE TABLE runs (
            run_id UUID PRIMARY KEY,
            stage VARCHAR NOT NULL,
            tenant_id VARCHAR,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            input_fingerprint VARCHAR,
            code_ref VARCHAR,
            config_hash VARCHAR,
            rows_in INTEGER,
            rows_out INTEGER,
            llm_calls INTEGER DEFAULT 0,
            tokens INTEGER DEFAULT 0,
            status VARCHAR NOT NULL,
            error TEXT,
            trace_id VARCHAR
        )
    """)

    # Create lineage table
    conn.execute("""
        CREATE TABLE lineage (
            child_run_id UUID NOT NULL,
            parent_run_id UUID NOT NULL,
            PRIMARY KEY (child_run_id, parent_run_id)
        )
    """)

    yield conn
    conn.close()


@pytest.fixture
def sample_table() -> ibis.Table:
    """Create sample Ibis table for testing."""
    return ibis.memtable(
        [
            {"author": "Alice", "message": "Hello world", "ts": "2025-01-01"},
            {"author": "Bob", "message": "Hi Alice", "ts": "2025-01-02"},
            {"author": "Alice", "message": "How are you?", "ts": "2025-01-03"},
        ]
    )


# ==============================================================================
# RunContext Tests
# ==============================================================================


def test_run_context_create():
    """RunContext.create() generates new run_id."""
    ctx1 = RunContext.create(stage="privacy", tenant_id="test")
    ctx2 = RunContext.create(stage="privacy", tenant_id="test")

    assert ctx1.run_id != ctx2.run_id  # Different runs
    assert ctx1.stage == "privacy"
    assert ctx1.tenant_id == "test"


def test_run_context_immutable():
    """RunContext is immutable (frozen dataclass)."""
    ctx = RunContext.create(stage="privacy")

    with pytest.raises(AttributeError):
        ctx.stage = "enrichment"  # Cannot modify frozen dataclass


def test_run_context_with_parents():
    """RunContext can track parent run IDs for lineage."""
    parent_id = uuid.uuid4()
    ctx = RunContext.create(
        stage="enrichment",
        parent_run_ids=[parent_id],
    )

    assert ctx.parent_run_ids == (parent_id,)  # Tuple (immutable)


# ==============================================================================
# record_run() Tests
# ==============================================================================


def test_record_run_minimal(runs_db: duckdb.DuckDBPyConnection):
    """record_run() writes minimal run record."""
    run_id = uuid.uuid4()
    started_at = datetime.now(UTC)

    record_run(
        conn=runs_db,
        run_id=run_id,
        stage="privacy",
        status="running",
        started_at=started_at,
    )

    # Verify record exists
    result = runs_db.execute(
        "SELECT run_id, stage, status FROM runs WHERE run_id = ?",
        [str(run_id)],
    ).fetchone()

    assert result is not None
    assert result[0] == run_id  # DuckDB returns UUID objects
    assert result[1] == "privacy"
    assert result[2] == "running"


def test_record_run_full_metadata(runs_db: duckdb.DuckDBPyConnection):
    """record_run() writes all metadata fields."""
    run_id = uuid.uuid4()
    started_at = datetime.now(UTC)
    finished_at = datetime.now(UTC)

    record_run(
        conn=runs_db,
        run_id=run_id,
        stage="enrichment",
        status="completed",
        started_at=started_at,
        finished_at=finished_at,
        tenant_id="acme",
        input_fingerprint="sha256:abc123",
        code_ref="a1b2c3d4",
        config_hash="sha256:def456",
        rows_in=100,
        rows_out=100,
        llm_calls=5,
        tokens=1200,
        trace_id="trace-xyz",
    )

    # Verify all fields
    result = runs_db.execute(
        """
        SELECT tenant_id, input_fingerprint, rows_in, rows_out, llm_calls, tokens
        FROM runs WHERE run_id = ?
        """,
        [str(run_id)],
    ).fetchone()

    assert result[0] == "acme"  # tenant_id
    assert result[1] == "sha256:abc123"  # input_fingerprint
    assert result[2] == 100  # rows_in
    assert result[3] == 100  # rows_out
    assert result[4] == 5  # llm_calls
    assert result[5] == 1200  # tokens


def test_record_run_auto_detects_git_commit(runs_db: duckdb.DuckDBPyConnection):
    """record_run() auto-detects git commit SHA if not provided."""
    run_id = uuid.uuid4()
    started_at = datetime.now(UTC)

    record_run(
        conn=runs_db,
        run_id=run_id,
        stage="privacy",
        status="completed",
        started_at=started_at,
        finished_at=started_at,
    )

    # Verify code_ref is populated (or None if not in git repo)
    result = runs_db.execute(
        "SELECT code_ref FROM runs WHERE run_id = ?",
        [str(run_id)],
    ).fetchone()

    code_ref = result[0]
    # If in git repo, should be 40-char SHA
    # If not in git repo, should be None
    assert code_ref is None or len(code_ref) == 40


# ==============================================================================
# record_lineage() Tests
# ==============================================================================


def test_record_lineage_single_parent(runs_db: duckdb.DuckDBPyConnection):
    """record_lineage() creates child → parent edge."""
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    # Create parent run first
    record_run(
        conn=runs_db,
        run_id=parent_id,
        stage="privacy",
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )

    # Create child run
    record_run(
        conn=runs_db,
        run_id=child_id,
        stage="enrichment",
        status="running",
        started_at=datetime.now(UTC),
    )

    # Record lineage
    record_lineage(
        conn=runs_db,
        child_run_id=child_id,
        parent_run_ids=[parent_id],
    )

    # Verify lineage edge
    result = runs_db.execute(
        "SELECT child_run_id, parent_run_id FROM lineage",
    ).fetchall()

    assert len(result) == 1
    assert result[0][0] == child_id  # DuckDB returns UUID objects
    assert result[0][1] == parent_id


def test_record_lineage_multiple_parents(runs_db: duckdb.DuckDBPyConnection):
    """record_lineage() supports multiple parents (join operation)."""
    parent1_id = uuid.uuid4()
    parent2_id = uuid.uuid4()
    child_id = uuid.uuid4()

    # Create parent runs
    for parent_id in [parent1_id, parent2_id]:
        record_run(
            conn=runs_db,
            run_id=parent_id,
            stage="privacy",
            status="completed",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )

    # Create child run
    record_run(
        conn=runs_db,
        run_id=child_id,
        stage="enrichment",
        status="running",
        started_at=datetime.now(UTC),
    )

    # Record lineage (multiple parents)
    record_lineage(
        conn=runs_db,
        child_run_id=child_id,
        parent_run_ids=[parent1_id, parent2_id],
    )

    # Verify both edges exist
    result = runs_db.execute(
        "SELECT child_run_id, parent_run_id FROM lineage ORDER BY parent_run_id",
    ).fetchall()

    assert len(result) == 2
    assert all(row[0] == child_id for row in result)  # DuckDB returns UUID objects


def test_record_lineage_no_parents(runs_db: duckdb.DuckDBPyConnection):
    """record_lineage() handles empty parent list (entry point)."""
    child_id = uuid.uuid4()

    # No error should occur
    record_lineage(
        conn=runs_db,
        child_run_id=child_id,
        parent_run_ids=[],
    )

    # No lineage edges created
    result = runs_db.execute("SELECT * FROM lineage").fetchall()
    assert len(result) == 0


# ==============================================================================
# Fingerprinting Tests
# ==============================================================================


def test_fingerprint_table_deterministic(sample_table: ibis.Table):
    """fingerprint_table() returns same hash for same table."""
    fp1 = fingerprint_table(sample_table)
    fp2 = fingerprint_table(sample_table)

    assert fp1 == fp2
    assert fp1.startswith("sha256:")


def test_fingerprint_table_different_data():
    """fingerprint_table() returns different hashes for different data."""
    table1 = ibis.memtable([{"author": "Alice", "message": "Hello"}])
    table2 = ibis.memtable([{"author": "Bob", "message": "Hi"}])

    fp1 = fingerprint_table(table1)
    fp2 = fingerprint_table(table2)

    assert fp1 != fp2


# ==============================================================================
# run_stage_with_tracking() Tests
# ==============================================================================


def test_run_stage_with_tracking_success(
    temp_db_path: Path,
    sample_table: ibis.Table,
):
    """run_stage_with_tracking() records successful stage execution."""
    # Create runs database
    conn = duckdb.connect(str(temp_db_path))
    conn.execute("""
        CREATE TABLE runs (
            run_id UUID PRIMARY KEY,
            stage VARCHAR NOT NULL,
            tenant_id VARCHAR,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            input_fingerprint VARCHAR,
            code_ref VARCHAR,
            config_hash VARCHAR,
            rows_in INTEGER,
            rows_out INTEGER,
            llm_calls INTEGER DEFAULT 0,
            tokens INTEGER DEFAULT 0,
            status VARCHAR NOT NULL,
            error TEXT,
            trace_id VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE lineage (
            child_run_id UUID NOT NULL,
            parent_run_id UUID NOT NULL,
            PRIMARY KEY (child_run_id, parent_run_id)
        )
    """)
    conn.close()

    # Define simple stage function
    def simple_stage(*, input_table: ibis.Table, **kwargs) -> ibis.Table:
        return input_table.mutate(processed=True)

    # Create context
    ctx = RunContext.create(stage="test-stage", db_path=temp_db_path)

    # Execute with tracking
    result, run_id = run_stage_with_tracking(
        stage_func=simple_stage,
        context=ctx,
        input_table=sample_table,
    )

    # Verify result
    assert isinstance(result, ibis.Table)
    assert run_id == ctx.run_id

    # Verify run record
    conn = duckdb.connect(str(temp_db_path))
    run_record = conn.execute(
        "SELECT stage, status, rows_in FROM runs WHERE run_id = ?",
        [str(run_id)],
    ).fetchone()

    assert run_record[0] == "test-stage"
    assert run_record[1] == "completed"
    assert run_record[2] == 3  # sample_table has 3 rows

    conn.close()


def test_run_stage_with_tracking_failure(temp_db_path: Path):
    """run_stage_with_tracking() records failures gracefully."""
    # Create runs database
    conn = duckdb.connect(str(temp_db_path))
    conn.execute("""
        CREATE TABLE runs (
            run_id UUID PRIMARY KEY,
            stage VARCHAR NOT NULL,
            tenant_id VARCHAR,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            input_fingerprint VARCHAR,
            code_ref VARCHAR,
            config_hash VARCHAR,
            rows_in INTEGER,
            rows_out INTEGER,
            llm_calls INTEGER DEFAULT 0,
            tokens INTEGER DEFAULT 0,
            status VARCHAR NOT NULL,
            error TEXT,
            trace_id VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE lineage (
            child_run_id UUID NOT NULL,
            parent_run_id UUID NOT NULL,
            PRIMARY KEY (child_run_id, parent_run_id)
        )
    """)
    conn.close()

    # Define failing stage function
    def failing_stage(*, input_table: ibis.Table, **kwargs) -> ibis.Table:
        raise ValueError("Intentional test failure")

    # Create context
    ctx = RunContext.create(stage="test-stage", db_path=temp_db_path)

    # Execute with tracking (should raise but record failure)
    with pytest.raises(ValueError, match="Intentional test failure"):
        run_stage_with_tracking(
            stage_func=failing_stage,
            context=ctx,
            input_table=None,
        )

    # Verify failure was recorded
    conn = duckdb.connect(str(temp_db_path))
    run_record = conn.execute(
        "SELECT status, error FROM runs WHERE run_id = ?",
        [str(ctx.run_id)],
    ).fetchone()

    assert run_record[0] == "failed"
    assert "ValueError: Intentional test failure" in run_record[1]

    conn.close()


def test_run_stage_with_tracking_records_lineage(temp_db_path: Path):
    """run_stage_with_tracking() records parent → child lineage."""
    # Create runs database
    conn = duckdb.connect(str(temp_db_path))
    conn.execute("""
        CREATE TABLE runs (
            run_id UUID PRIMARY KEY,
            stage VARCHAR NOT NULL,
            tenant_id VARCHAR,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            input_fingerprint VARCHAR,
            code_ref VARCHAR,
            config_hash VARCHAR,
            rows_in INTEGER,
            rows_out INTEGER,
            llm_calls INTEGER DEFAULT 0,
            tokens INTEGER DEFAULT 0,
            status VARCHAR NOT NULL,
            error TEXT,
            trace_id VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE lineage (
            child_run_id UUID NOT NULL,
            parent_run_id UUID NOT NULL,
            PRIMARY KEY (child_run_id, parent_run_id)
        )
    """)
    conn.close()

    # Create parent run
    parent_id = uuid.uuid4()
    conn = duckdb.connect(str(temp_db_path))
    record_run(
        conn=conn,
        run_id=parent_id,
        stage="parent-stage",
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    conn.close()

    # Define simple stage function
    def child_stage(*, input_table: ibis.Table | None, **kwargs) -> str:
        return "success"

    # Create context with parent
    ctx = RunContext.create(
        stage="child-stage",
        parent_run_ids=[parent_id],
        db_path=temp_db_path,
    )

    # Execute with tracking
    result, run_id = run_stage_with_tracking(
        stage_func=child_stage,
        context=ctx,
        input_table=None,
    )

    # Verify lineage was recorded
    conn = duckdb.connect(str(temp_db_path))
    lineage_record = conn.execute(
        "SELECT child_run_id, parent_run_id FROM lineage",
    ).fetchone()

    assert lineage_record[0] == run_id  # DuckDB returns UUID objects
    assert lineage_record[1] == parent_id

    conn.close()


# ==============================================================================
# Git Integration Tests
# ==============================================================================


def test_get_git_commit_sha():
    """get_git_commit_sha() returns SHA or None."""
    sha = get_git_commit_sha()

    # If in git repo, should be 40-char hex string
    # If not in git repo, should be None
    assert sha is None or (isinstance(sha, str) and len(sha) == 40)
