"""Data access layer for pipeline run history."""

from pathlib import Path

import duckdb


class RunStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        if not self.db_path.exists():
            raise FileNotFoundError(f"No runs database found at {self.db_path}")
        self.conn = duckdb.connect(str(self.db_path), read_only=True)

        # Detect schema version by checking for v2 columns
        self._has_v2_schema = self._check_v2_schema()

    def _check_v2_schema(self) -> bool:
        """Check if database has v2.0.0 schema (parent_run_id, duration_seconds, attrs)."""
        try:
            result = self.conn.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'runs'
                  AND column_name IN ('parent_run_id', 'duration_seconds', 'attrs')
            """).fetchall()
            # If we have all 3 v2 columns, it's a v2 schema
            return len(result) == 3
        except Exception:  # noqa: BLE001
            # If query fails, assume legacy schema
            return False

    def get_latest_runs(self, n: int = 10):
        """Fetches the last N runs from the database."""
        if self._has_v2_schema:
            query = """
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
            """
        else:
            # Legacy v1 schema (compute duration from timestamps)
            query = """
                SELECT
                    run_id,
                    stage,
                    status,
                    started_at,
                    rows_in,
                    rows_out,
                    EXTRACT(EPOCH FROM (finished_at - started_at)) AS duration_seconds
                FROM runs
                WHERE started_at IS NOT NULL
                ORDER BY started_at DESC
                LIMIT ?
            """
        return self.conn.execute(query, [n]).fetchall()

    def get_run_by_id(self, run_id: str):
        """Fetches a single run by its full or partial UUID."""
        if self._has_v2_schema:
            query = """
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
            """
        else:
            # Legacy v1 schema (without parent_run_id, duration_seconds, attrs)
            query = """
                SELECT
                    run_id,
                    tenant_id,
                    stage,
                    status,
                    error,
                    NULL AS parent_run_id,
                    code_ref,
                    config_hash,
                    started_at,
                    finished_at,
                    EXTRACT(EPOCH FROM (finished_at - started_at)) AS duration_seconds,
                    rows_in,
                    rows_out,
                    llm_calls,
                    tokens,
                    NULL AS attrs,
                    trace_id
                FROM runs
                WHERE CAST(run_id AS VARCHAR) LIKE ?
                ORDER BY started_at DESC
                LIMIT 1
            """
        return self.conn.execute(query, [f"{run_id}%"]).fetchone()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
