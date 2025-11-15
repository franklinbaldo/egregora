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
            WITH run_summary AS (
                SELECT
                    run_id,
                    stage,
                    LAST(status ORDER BY timestamp) as status,
                    MIN(CASE WHEN status = 'started' THEN timestamp END) as started_at,
                    MAX(CASE WHEN status = 'started' THEN rows_in END) as rows_in,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN rows_out END) as rows_out,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN duration_seconds END) as duration_seconds
                FROM run_events
                GROUP BY run_id, stage
            )
            SELECT *
            FROM run_summary
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
            WITH run_events_filtered AS (
                SELECT *
                FROM run_events
                WHERE CAST(run_id AS VARCHAR) LIKE ?
            ),
            run_summary AS (
                SELECT
                    run_id,
                    MAX(tenant_id) as tenant_id,
                    stage,
                    LAST(status ORDER BY timestamp) as status,
                    LAST(error ORDER BY timestamp) FILTER (WHERE error IS NOT NULL) as error,
                    MAX(CASE WHEN status = 'started' THEN input_fingerprint END) as input_fingerprint,
                    MAX(code_ref) as code_ref,
                    MAX(config_hash) as config_hash,
                    MIN(CASE WHEN status = 'started' THEN timestamp END) as started_at,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN timestamp END) as finished_at,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN duration_seconds END) as duration_seconds,
                    MAX(CASE WHEN status = 'started' THEN rows_in END) as rows_in,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN rows_out END) as rows_out,
                    MAX(llm_calls) as llm_calls,
                    MAX(tokens) as tokens,
                    MAX(trace_id) as trace_id
                FROM run_events_filtered
                GROUP BY run_id, stage
            )
            SELECT *
            FROM run_summary
            WHERE started_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 1
            """,
            [f"{run_id}%"],
        ).fetchone()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
