"""Pipeline run tracking with observability and lineage.

This module provides infrastructure for tracking pipeline execution:
1. Record run metadata (stage, duration, metrics, errors)
2. Track lineage relationships (which runs depend on which)
3. Content-addressed checkpointing (skip stages if output exists)
4. OpenTelemetry integration (traces, logs)

Usage:
    from egregora.database.tracking import RunContext, record_run, run_stage_with_tracking

    # Create run context
    ctx = RunContext.create(stage="privacy", tenant_id="acme")

    # Execute stage with automatic tracking
    result, run_id = run_stage_with_tracking(
        stage_func=privacy_gate_stage,
        input_table=raw_data,
        context=ctx,
    )

    # Record run metadata manually
    record_run(
        conn=duckdb_conn,
        run_id=uuid.uuid4(),
        stage="enrichment",
        status="completed",
        started_at=start_time,
        finished_at=end_time,
    )
"""

import hashlib
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import duckdb
import ibis

# Type variable for stage function return type
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RunContext:
    """Immutable context for pipeline run tracking.

    Created once at pipeline start, passed to all stages.
    Contains run-specific metadata for lineage and observability.
    """

    run_id: uuid.UUID
    """Unique identifier for this run (immutable)."""

    stage: str
    """Pipeline stage identifier (ingestion, privacy, enrichment, etc.)."""

    tenant_id: str | None = None
    """Tenant identifier for multi-tenant isolation."""

    parent_run_ids: tuple[uuid.UUID, ...] = ()
    """Parent run IDs (upstream dependencies for lineage tracking)."""

    db_path: Path | None = None
    """Path to DuckDB database for run tracking (default: .egregora-cache/runs.duckdb)."""

    trace_id: str | None = None
    """OpenTelemetry trace ID for distributed tracing."""

    @classmethod
    def create(
        cls,
        stage: str,
        tenant_id: str | None = None,
        parent_run_ids: list[uuid.UUID] | None = None,
        db_path: Path | None = None,
        trace_id: str | None = None,
    ) -> "RunContext":
        """Create a new run context with generated run_id.

        Args:
            stage: Pipeline stage identifier
            tenant_id: Tenant identifier (optional)
            parent_run_ids: Parent run IDs for lineage (optional)
            db_path: DuckDB database path (default: .egregora-cache/runs.duckdb)
            trace_id: OpenTelemetry trace ID (optional)

        Returns:
            Immutable RunContext instance

        Example:
            >>> ctx = RunContext.create(stage="privacy", tenant_id="acme")
            >>> result, run_id = run_stage_with_tracking(
            ...     stage_func=privacy_gate_stage,
            ...     context=ctx,
            ...     input_table=raw_data,
            ...     config=privacy_config,
            ... )

        """
        return cls(
            run_id=uuid.uuid4(),
            stage=stage,
            tenant_id=tenant_id,
            parent_run_ids=tuple(parent_run_ids or []),
            db_path=db_path or Path(".egregora-cache/runs.duckdb"),
            trace_id=trace_id,
        )


from egregora.utils.git import get_git_commit_sha




def record_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: uuid.UUID,
    stage: str,
    status: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    *,
    tenant_id: str | None = None,
    input_fingerprint: str | None = None,
    code_ref: str | None = None,
    config_hash: str | None = None,
    rows_in: int | None = None,
    rows_out: int | None = None,
    llm_calls: int = 0,
    tokens: int = 0,
    error: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Record run metadata to runs table.

    Args:
        conn: DuckDB connection
        run_id: Unique run identifier
        stage: Pipeline stage (ingestion, privacy, enrichment, etc.)
        status: Run status (running, completed, failed, degraded)
        started_at: When run started (UTC)
        finished_at: When run finished (UTC), None if still running
        tenant_id: Tenant identifier (optional)
        input_fingerprint: SHA256 of input data (for checkpointing)
        code_ref: Git commit SHA
        config_hash: SHA256 of config
        rows_in: Number of input rows
        rows_out: Number of output rows
        llm_calls: Number of LLM API calls
        tokens: Total tokens consumed
        error: Error message if status=failed
        trace_id: OpenTelemetry trace ID

    Raises:
        duckdb.Error: If insert fails

    """
    # Ensure runs table exists (idempotent)
    from egregora.database.ir_schema import ensure_runs_table_exists

    ensure_runs_table_exists(conn)

    # Auto-detect code_ref if not provided
    if code_ref is None:
        code_ref = get_git_commit_sha()

    # Calculate duration if both timestamps provided
    duration_seconds = None
    if started_at and finished_at:
        duration_seconds = (finished_at - started_at).total_seconds()

    # Insert run record
    conn.execute(
        """
        INSERT INTO runs (
            run_id, tenant_id, stage, status, error,
            input_fingerprint, code_ref, config_hash,
            started_at, finished_at, duration_seconds,
            rows_in, rows_out, llm_calls, tokens, trace_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(run_id),
            tenant_id,
            stage,
            status,
            error,
            input_fingerprint,
            code_ref,
            config_hash,
            started_at,
            finished_at,
            duration_seconds,
            rows_in,
            rows_out,
            llm_calls,
            tokens,
            trace_id,
        ],
    )


def record_lineage(
    conn: duckdb.DuckDBPyConnection,
    child_run_id: uuid.UUID,
    parent_run_ids: list[uuid.UUID],
) -> None:
    """Record lineage relationships between runs.

    Args:
        conn: DuckDB connection
        child_run_id: Downstream run ID (depends on parents)
        parent_run_ids: Upstream run IDs (dependencies)

    Raises:
        duckdb.Error: If insert fails

    """
    if not parent_run_ids:
        return  # No lineage to record

    # Ensure lineage table exists (idempotent)
    from egregora.database.ir_schema import ensure_lineage_table_exists

    ensure_lineage_table_exists(conn)

    # Insert lineage edges
    for parent_id in parent_run_ids:
        conn.execute(
            """
            INSERT INTO lineage (child_run_id, parent_run_id)
            VALUES (?, ?)
            ON CONFLICT DO NOTHING
            """,
            [str(child_run_id), str(parent_id)],
        )


from contextlib import contextmanager

@contextmanager
def track_stage_run(context: RunContext, input_table: ibis.Table | None = None):
    """A context manager to automatically track the start, success, and failure of a stage."""
    db_path = context.db_path or Path(".egregora-cache/runs.duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    from egregora.utils.fingerprinting import fingerprint_table
    input_fingerprint = fingerprint_table(input_table) if input_table is not None else None
    rows_in = input_table.count().execute() if input_table is not None else None

    started_at = datetime.now(UTC)
    record_run(
        conn=conn, run_id=context.run_id, stage=context.stage, status="running",
        started_at=started_at, tenant_id=context.tenant_id,
        input_fingerprint=input_fingerprint, rows_in=rows_in, trace_id=context.trace_id,
    )

    if context.parent_run_ids:
        record_lineage(conn=conn, child_run_id=context.run_id, parent_run_ids=list(context.parent_run_ids))

    try:
        yield
        finished_at = datetime.now(UTC)
        duration = (finished_at - started_at).total_seconds()
        conn.execute("UPDATE runs SET status = 'completed', finished_at = ?, duration_seconds = ? WHERE run_id = ?", [finished_at, duration, str(context.run_id)])
    except Exception as e:
        finished_at = datetime.now(UTC)
        duration = (finished_at - started_at).total_seconds()
        error_msg = f"{type(e).__name__}: {e!s}"
        conn.execute("UPDATE runs SET status = 'failed', finished_at = ?, duration_seconds = ?, error = ? WHERE run_id = ?", [finished_at, duration, error_msg, str(context.run_id)])
        raise
    finally:
        conn.close()

def run_stage_with_tracking[T](
    stage_func: Callable[..., T], *, context: RunContext,
    input_table: ibis.Table | None = None, **kwargs: Any
) -> tuple[T, uuid.UUID]:
    """Executes a pipeline stage with automatic run tracking using a context manager."""
    with track_stage_run(context, input_table):
        result = stage_func(input_table=input_table, **kwargs)

        # This part is a bit tricky, as we need to update the run record with the output rows.
        # A more advanced implementation might pass a "run_tracker" object to the context manager
        # that can be used to update the record. For now, we'll just re-open the connection.
        db_path = context.db_path or Path(".egregora-cache/runs.duckdb")
        conn = duckdb.connect(str(db_path))
        try:
            if isinstance(result, ibis.Table):
                rows_out = result.count().execute()
                conn.execute("UPDATE runs SET rows_out = ? WHERE run_id = ?", [rows_out, str(context.run_id)])
        finally:
            conn.close()

    return result, context.run_id
