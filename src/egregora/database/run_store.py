"""Data access layer for pipeline run history."""

from pathlib import Path

import duckdb


class RunStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        if not self.db_path.exists():
            raise FileNotFoundError(f"No runs database found at {self.db_path}")
        self.conn = duckdb.connect(str(self.db_path), read_only=True)
        self._columns = self._load_columns()

    def _load_columns(self) -> set[str]:
        """Return available columns for the runs table."""
        columns = self.conn.execute("PRAGMA table_info('runs')").fetchall()
        # DuckDB PRAGMA table_info returns rows like:
        #   column_name, column_type, null, key, default
        return {row[0] for row in columns}

    def _has_column(self, name: str) -> bool:
        return name in self._columns

    def _column_or_null(self, name: str, duck_type: str) -> str:
        """Return column name or a typed NULL alias if missing."""
        if self._has_column(name):
            return name
        return f"CAST(NULL AS {duck_type}) AS {name}"

    def _duration_expression(self) -> str:
        """Return a safe duration expression compatible with old schemas."""
        if self._has_column("duration_seconds"):
            return "duration_seconds"
        if self._has_column("started_at") and self._has_column("finished_at"):
            return "CAST(date_diff('second', started_at, finished_at) AS DOUBLE) AS duration_seconds"
        return "CAST(NULL AS DOUBLE) AS duration_seconds"

    def get_latest_runs(self, n: int = 10):
        """Fetches the last N runs from the database."""
        duration_expr = self._duration_expression()
        return self.conn.execute(
            """
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
            """.format(duration_expr=duration_expr),
            [n],
        ).fetchall()

    def get_run_by_id(self, run_id: str):
        """Fetches a single run by its full or partial UUID."""
        parent_run_expr = self._column_or_null("parent_run_id", "UUID")
        duration_expr = self._duration_expression()
        attrs_expr = self._column_or_null("attrs", "JSON")
        return self.conn.execute(
            """
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
            """.format(
                parent_run_expr=parent_run_expr,
                duration_expr=duration_expr,
                attrs_expr=attrs_expr,
            ),
            [f"{run_id}%"],
        ).fetchone()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
