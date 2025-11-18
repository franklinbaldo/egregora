"""Data access layer for pipeline run history."""

from pathlib import Path

import duckdb


class RunStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        if not self.db_path.exists():
            raise FileNotFoundError(f"No runs database found at {self.db_path}")
        self.conn = duckdb.connect(str(self.db_path), read_only=True)

    def get_latest_runs(self, n: int = 10):
        """Fetches the last N runs from the database."""
        return self.conn.execute(
            """
            SELECT
                run_id,
                stage,
                status,
                started_at,
                rows_in,
                rows_out,
                duration_seconds
            FROM runs
            WHERE started_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT ?
            """,
            [n],
        ).fetchall()

    def get_run_by_id(self, run_id: str):
        """Fetches a single run by its full or partial UUID."""
        return self.conn.execute(
            """
            SELECT
                run_id,
                tenant_id,
                stage,
                status,
                error,
                parent_run_id,
                code_ref,
                config_hash,
                started_at,
                finished_at,
                duration_seconds,
                rows_in,
                rows_out,
                llm_calls,
                tokens,
                attrs,
                trace_id
            FROM runs
            WHERE CAST(run_id AS VARCHAR) LIKE ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            [f"{run_id}%"],
        ).fetchone()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
