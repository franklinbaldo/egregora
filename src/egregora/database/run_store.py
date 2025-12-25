"""Data access layer for pipeline run history.

This module encapsulates all domain-specific SQL logic for querying and updating
the 'runs' table, preventing leakage of application schema details into the
generic storage manager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self
from dataclasses import dataclass
from datetime import datetime
import uuid

from egregora.database.utils import get_git_commit_sha
from egregora.database.ir_schema import ensure_runs_table_exists

if TYPE_CHECKING:
    # Use Protocol for abstraction instead of concrete implementation
    from egregora.database.protocols import StorageProtocol


@dataclass
class RunMetadata:
    """Metadata for a single run recording."""

    run_id: uuid.UUID
    stage: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    tenant_id: str | None = None
    code_ref: str | None = None
    config_hash: str | None = None
    rows_in: int | None = None
    rows_out: int | None = None
    llm_calls: int = 0
    tokens: int = 0
    error: str | None = None
    trace_id: str | None = None


class RunStore:
    """Repository for run tracking operations.

    Abstracts run persistence logic away from the orchestration layer,
    working with any storage backend that implements StorageProtocol.
    """

    def __init__(self, storage: StorageProtocol) -> None:
        """Initialize run store with a storage backend.

        Args:
            storage: Storage backend implementing StorageProtocol

        """
        self.storage = storage

    def _runs_duration_expression(self) -> str:
        columns = self.storage.get_table_columns("runs")
        if "duration_seconds" in columns:
            return "duration_seconds"
        if "started_at" in columns and "finished_at" in columns:
            return "CAST(date_diff('second', started_at, finished_at) AS DOUBLE) AS duration_seconds"
        return "CAST(NULL AS DOUBLE) AS duration_seconds"

    def _column_or_null(self, table_name: str, column: str, duck_type: str) -> str:
        columns = self.storage.get_table_columns(table_name)
        if column in columns:
            return column
        return f"CAST(NULL AS {duck_type}) AS {column}"

    def get_latest_runs(self, n: int = 10) -> list[tuple]:
        """Fetches the last N runs from the database."""
        duration_expr = self._runs_duration_expression()
        sql = f"""
            SELECT
                run_id,
                stage,
                status,
                started_at,
                rows_in,
                rows_out,
                {duration_expr}
            FROM runs
            WHERE started_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT ?
        """
        return self.storage.execute_query(sql, [n])

    def get_run_by_id(self, run_id: str) -> tuple | None:
        """Fetches a single run by its full or partial UUID."""
        parent_run_expr = self._column_or_null("runs", "parent_run_id", "UUID")
        duration_expr = self._runs_duration_expression()
        attrs_expr = self._column_or_null("runs", "attrs", "JSON")
        sql = f"""
            SELECT
                run_id,
                tenant_id,
                stage,
                status,
                error,
                {parent_run_expr},
                code_ref,
                config_hash,
                started_at,
                finished_at,
                {duration_expr},
                rows_in,
                rows_out,
                llm_calls,
                tokens,
                {attrs_expr},
                trace_id
            FROM runs
            WHERE CAST(run_id AS VARCHAR) LIKE ?
            ORDER BY started_at DESC
            LIMIT 1
        """
        return self.storage.execute_query_single(sql, [f"{run_id}%"])

    def record_run(self, metadata: RunMetadata) -> None:
        """Record run metadata to runs table."""
        with self.storage.connection() as resolved_conn:
            ensure_runs_table_exists(resolved_conn)

            # Auto-detect code_ref if not provided
            code_ref = metadata.code_ref or get_git_commit_sha()

            # Calculate duration if both timestamps provided
            duration_seconds = None
            if metadata.started_at and metadata.finished_at:
                duration_seconds = (metadata.finished_at - metadata.started_at).total_seconds()

            # Insert run record
            resolved_conn.execute(
                "INSERT INTO runs (run_id, tenant_id, stage, status, error, code_ref, config_hash, started_at, finished_at, duration_seconds, rows_in, rows_out, llm_calls, tokens, trace_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    str(metadata.run_id),
                    metadata.tenant_id,
                    metadata.stage,
                    metadata.status,
                    metadata.error,
                    code_ref,
                    metadata.config_hash,
                    metadata.started_at,
                    metadata.finished_at,
                    duration_seconds,
                    metadata.rows_in,
                    metadata.rows_out,
                    metadata.llm_calls,
                    metadata.tokens,
                    metadata.trace_id,
                ],
            )

    def mark_run_started(
        self,
        *,
        run_id: uuid.UUID,
        stage: str,
        started_at: datetime,
        rows_in: int | None = None,
        tenant_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Record the start of a pipeline run."""
        metadata = RunMetadata(
            run_id=run_id,
            stage=stage,
            status="running",
            started_at=started_at,
            rows_in=rows_in,
            tenant_id=tenant_id,
            trace_id=trace_id,
        )
        self.record_run(metadata)

    def mark_run_completed(
        self,
        *,
        run_id: uuid.UUID,
        finished_at: datetime,
        duration_seconds: float,
        rows_out: int | None,
    ) -> None:
        """Update run record when a stage completes."""
        sql = "UPDATE runs SET status = 'completed', finished_at = ?, duration_seconds = ?, rows_out = ? WHERE run_id = ?"
        self.storage.execute_query(sql, [finished_at, duration_seconds, rows_out, str(run_id)])

    def mark_run_failed(
        self,
        *,
        run_id: uuid.UUID,
        finished_at: datetime,
        duration_seconds: float,
        error: str,
    ) -> None:
        """Update runs when a stage fails."""
        sql = "UPDATE runs SET status = 'failed', finished_at = ?, duration_seconds = ?, error = ? WHERE run_id = ?"
        self.storage.execute_query(sql, [finished_at, duration_seconds, error, str(run_id)])

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type: object, _exc_val: object, _exc_tb: object) -> None:
        pass
