"""Pipeline run tracking with observability and lineage.

This module provides infrastructure for tracking pipeline execution:
1. Record run metadata (stage, duration, metrics, errors)
2. Track lineage relationships (which runs depend on which)
3. OpenTelemetry integration (traces, logs)

Usage:
    from egregora.database.tracking import RunContext, run_stage_with_tracking

    # Create run context
    ctx = RunContext.create(stage="privacy", tenant_id="acme")

    # Execute stage with automatic tracking
    result, run_id = run_stage_with_tracking(
        stage_func=privacy_gate_stage,
        input_table=raw_data,
        context=ctx,
    )
"""

import contextlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

import duckdb
import ibis

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.ir_schema import ensure_lineage_table_exists
from egregora.database.run_store import RunStore, RunMetadata


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

    trace_id: str | None = None
    """OpenTelemetry trace ID for distributed tracing."""

    @classmethod
    def create(
        cls,
        stage: str,
        tenant_id: str | None = None,
        parent_run_ids: list[uuid.UUID] | None = None,
        trace_id: str | None = None,
    ) -> "RunContext":
        """Create a new run context with generated run_id.

        Args:
            stage: Pipeline stage identifier
            tenant_id: Tenant identifier (optional)
            parent_run_ids: Parent run IDs for lineage (optional)
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
            trace_id=trace_id,
        )


@contextlib.contextmanager
def _connection_scope(
    conn: duckdb.DuckDBPyConnection | DuckDBStorageManager,
) -> duckdb.DuckDBPyConnection:
    """Yield a DuckDB connection from either a manager or connection.

    Uses duck typing instead of isinstance() to support any storage backend
    that provides a connection() context manager.
    """
    # Duck typing: check for connection() method instead of concrete type
    if hasattr(conn, "connection") and callable(conn.connection):
        with conn.connection() as managed_conn:
            yield managed_conn
    else:
        # Assume it's already a connection object
        yield conn


def _ensure_lineage_table(conn: duckdb.DuckDBPyConnection) -> None:
    ensure_lineage_table_exists(conn)


def record_lineage(
    conn: duckdb.DuckDBPyConnection | DuckDBStorageManager,
    child_run_id: uuid.UUID,
    parent_run_ids: list[uuid.UUID],
) -> None:
    """Record lineage relationships between runs.

    Args:
        conn: DuckDB connection or :class:`DuckDBStorageManager`
        child_run_id: Downstream run ID (depends on parents)
        parent_run_ids: Upstream run IDs (dependencies)

    Raises:
        duckdb.Error: If insert fails

    """
    if not parent_run_ids:
        return  # No lineage to record

    # Ensure lineage table exists (idempotent)
    with _connection_scope(conn) as resolved_conn:
        _ensure_lineage_table(resolved_conn)

        # Insert lineage edges
        for parent_id in parent_run_ids:
            resolved_conn.execute(
                "INSERT INTO lineage (child_run_id, parent_run_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
                [str(child_run_id), str(parent_id)],
            )


def run_stage_with_tracking[T](
    stage_func: Callable[..., T],
    *,
    context: RunContext,
    run_store: "RunStore",
    input_table: ibis.Table | None = None,
    **kwargs: Any,
) -> tuple[T, uuid.UUID]:
    """Execute a pipeline stage with automatic run tracking.

    This wrapper:
    1. Records run start (status=running)
    2. Executes stage function
    3. Records run completion (status=completed/failed)
    4. Records lineage relationships
    5. Handles errors gracefully

    Args:
        stage_func: Pipeline stage function to execute
        context: Run context with metadata
        run_store: The repository for run tracking operations.
        input_table: Input Ibis table (for fingerprinting, optional)
        **kwargs: Additional arguments to pass to stage_func

    Returns:
        (result, run_id): Stage function result + run ID

    Raises:
        Exception: Re-raises any exception from stage_func after recording failure

    Example:
        >>> ctx = RunContext.create(stage="privacy", tenant_id="acme")
        >>> result, run_id = run_stage_with_tracking(
        ...     stage_func=privacy_gate_stage,
        ...     context=ctx,
        ...     run_store=run_store,
        ...     input_table=raw_data,
        ...     config=privacy_config,
        ... )

    """
    # Calculate input metrics
    rows_in = None
    if input_table is not None:
        rows_in = input_table.count().execute()

    # Record run start
    started_at = datetime.now(UTC)
    run_store.mark_run_started(
        run_id=context.run_id,
        stage=context.stage,
        started_at=started_at,
        rows_in=rows_in,
        tenant_id=context.tenant_id,
        trace_id=context.trace_id,
    )

    # Record lineage (if parent runs exist)
    if context.parent_run_ids:
        record_lineage(
            conn=run_store.storage,
            child_run_id=context.run_id,
            parent_run_ids=list(context.parent_run_ids),
        )

    try:
        # Execute stage function
        result = stage_func(input_table=input_table, **kwargs)

        # Record success
        finished_at = datetime.now(UTC)
        duration_seconds = (finished_at - started_at).total_seconds()

        # Calculate output rows if result is Ibis table
        rows_out = None
        if isinstance(result, ibis.Table):
            rows_out = result.count().execute()

        # Update run record (completed)
        run_store.mark_run_completed(
            run_id=context.run_id,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            rows_out=rows_out,
        )
    except Exception as e:
        # Record failure
        finished_at = datetime.now(UTC)
        duration_seconds = (finished_at - started_at).total_seconds()
        error_msg = f"{type(e).__name__}: {e!s}"

        run_store.mark_run_failed(
            run_id=context.run_id,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            error=error_msg,
        )

        raise  # Re-raise exception after recording
    else:
        return result, context.run_id
