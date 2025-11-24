"""Data access layer for pipeline run history.

This module encapsulates all domain-specific SQL logic for querying and updating
the 'runs' table, preventing leakage of application schema details into the
generic storage manager.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager


class RunStore:
    def __init__(self, storage: DuckDBStorageManager) -> None:
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

    def mark_run_completed(
        self,
        *,
        run_id: uuid.UUID,
        finished_at: datetime,
        duration_seconds: float,
        rows_out: int | None,
    ) -> None:
        """Update ``runs`` when a stage completes."""
        sql = """
            UPDATE runs
            SET status = 'completed',
                finished_at = ?,
                duration_seconds = ?,
                rows_out = ?
            WHERE run_id = ?
        """
        self.storage.execute_query(sql, [finished_at, duration_seconds, rows_out, str(run_id)])

    def mark_run_failed(
        self,
        *,
        run_id: uuid.UUID,
        finished_at: datetime,
        duration_seconds: float,
        error: str,
    ) -> None:
        """Update ``runs`` when a stage fails."""
        sql = """
            UPDATE runs
            SET status = 'failed',
                finished_at = ?,
                duration_seconds = ?,
                error = ?
            WHERE run_id = ?
        """
        self.storage.execute_query(sql, [finished_at, duration_seconds, error, str(run_id)])

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass
