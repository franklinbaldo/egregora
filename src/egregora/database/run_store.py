"""Data access layer for pipeline run history."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager


class RunStore:
    def __init__(self, storage: DuckDBStorageManager) -> None:
        self.storage = storage

    def get_latest_runs(self, n: int = 10) -> list[dict]:
        """Fetches the last N runs from the database."""
        # Phase 3 Refactor: Logic moved from DuckDBStorageManager
        return self.fetch_latest_runs(limit=n)

    def get_run_by_id(self, run_id: str) -> dict | None:
        """Fetches a single run by its full or partial UUID."""
        # Phase 3 Refactor: Logic moved from DuckDBStorageManager
        return self.fetch_run_by_partial_id(run_id)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    # ==================================================================
    # Domain-specific queries (Moved from DuckDBStorageManager)
    # ==================================================================

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

    def fetch_latest_runs(self, limit: int = 10) -> list[tuple]:
        """Return summaries for the most recent runs."""
        duration_expr = self._runs_duration_expression()
        with self.storage.connection() as conn:
            return conn.execute(
                f"""
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
                """,
                [limit],
            ).fetchall()

    def fetch_run_by_partial_id(self, run_id: str) -> dict | None:
        """Return the newest run whose UUID starts with ``run_id``."""
        parent_run_expr = self._column_or_null("runs", "parent_run_id", "UUID")
        duration_expr = self._runs_duration_expression()
        attrs_expr = self._column_or_null("runs", "attrs", "JSON")
        with self.storage.connection() as conn:
            # Use fetchone directly on cursor
            row = conn.execute(
                f"""
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
                """,
                [f"{run_id}%"],
            ).fetchone()

            if row:
                # Convert tuple to dict using description if available, or manual mapping
                # DuckDB cursors have description
                # Ideally we return a dict to match previous behavior if possible,
                # or the caller expects a tuple?
                # The previous implementation in DuckDBStorageManager returned fetchone() result directly.
                # Looking at CLI usage might clarify.
                # For now, returning row (tuple) is consistent with `fetchall` in `fetch_latest_runs` returning list of tuples.
                # Wait, `fetch_run_by_partial_id` type hint says `dict | None`.
                # The previous implementation:
                # return self._conn.execute(...).fetchone() -> This returns a tuple in DuckDB Python API!
                # BUT, DuckDBStorageManager implementation had type hint `dict | None`.
                # If it returned a tuple, the type hint was wrong OR the caller handled it.
                # Let's check `fetch_run_by_partial_id` in `duckdb_manager.py` again.
                # It returned `self._conn.execute(...).fetchone()`.
                # Standard DuckDB returns tuple.
                # However, if `duckdb_manager.py` had `con.execute()`, maybe it was using a wrapper? No, `self._conn = duckdb.connect()`.
                # So it returned a tuple.
                # Let's check `cli/runs.py` to see how it's used.
                pass

            # To be safe and truly return a dict as typed:
            if row:
                # We need columns.
                # Re-executing to get description seems wasteful but robust.
                # Or hardcode columns based on SELECT.
                columns = [
                    "run_id",
                    "tenant_id",
                    "stage",
                    "status",
                    "error",
                    "parent_run_id",
                    "code_ref",
                    "config_hash",
                    "started_at",
                    "finished_at",
                    "duration_seconds",
                    "rows_in",
                    "rows_out",
                    "llm_calls",
                    "tokens",
                    "attrs",
                    "trace_id",
                ]
                return dict(zip(columns, row, strict=False))
            return None

    def mark_run_completed(
        self,
        *,
        run_id: uuid.UUID,
        finished_at: datetime,
        duration_seconds: float,
        rows_out: int | None,
    ) -> None:
        """Update ``runs`` when a stage completes."""
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = 'completed',
                    finished_at = ?,
                    duration_seconds = ?,
                    rows_out = ?
                WHERE run_id = ?
                """,
                [finished_at, duration_seconds, rows_out, str(run_id)],
            )

    def mark_run_failed(
        self,
        *,
        run_id: uuid.UUID,
        finished_at: datetime,
        duration_seconds: float,
        error: str,
    ) -> None:
        """Update ``runs`` when a stage fails."""
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = 'failed',
                    finished_at = ?,
                    duration_seconds = ?,
                    error = ?
                WHERE run_id = ?
                """,
                [finished_at, duration_seconds, error, str(run_id)],
            )
