"""Data access layer for pipeline run history.

This module encapsulates all domain-specific SQL logic for querying and updating
the 'runs' table, preventing leakage of application schema details into the
generic storage manager.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Self

import ibis
from ibis import _

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.database.duckdb_manager import DuckDBStorageManager


class RunStore:
    def __init__(self, storage: DuckDBStorageManager) -> None:
        self.storage = storage

    def _duration_expression(self, runs_table: Table):
        columns = set(runs_table.columns)
        if "duration_seconds" in columns:
            return runs_table.duration_seconds

        if "started_at" in columns and "finished_at" in columns:
            duration = (runs_table.finished_at - runs_table.started_at).to_unit("s")
            return duration.cast("float64").name("duration_seconds")

        return ibis.null().cast("float64").name("duration_seconds")

    def _column_or_null(self, table: Table, column: str, ibis_type: str):
        columns = set(table.columns)
        if column in columns:
            return table[column]
        return ibis.null().cast(ibis_type).name(column)

    def get_latest_runs(self, n: int = 10) -> list[tuple]:
        """Fetches the last N runs from the database."""
        runs_table = self.storage.read_table("runs")
        duration_expr = self._duration_expression(runs_table)

        query = (
            runs_table.filter(_.started_at.notnull())
            .select(
                _.run_id,
                _.stage,
                _.status,
                _.started_at,
                _.rows_in,
                _.rows_out,
                duration_expr,
            )
            .order_by(_.started_at.desc())
            .limit(n)
        )

        result = query.execute()
        return [tuple(row) for row in result.itertuples(index=False, name=None)]

    def get_run_by_id(self, run_id: str) -> tuple | None:
        """Fetches a single run by its full or partial UUID."""
        runs_table = self.storage.read_table("runs")
        parent_run_expr = self._column_or_null(runs_table, "parent_run_id", "uuid")
        duration_expr = self._duration_expression(runs_table)
        attrs_expr = self._column_or_null(runs_table, "attrs", "json")
        run_id_literal = ibis.literal(str(run_id))

        query = (
            runs_table.filter(_.run_id.cast("string").like(run_id_literal + "%"))
            .select(
                _.run_id,
                _.tenant_id,
                _.stage,
                _.status,
                _.error,
                parent_run_expr,
                _.code_ref,
                _.config_hash,
                _.started_at,
                _.finished_at,
                duration_expr,
                _.rows_in,
                _.rows_out,
                _.llm_calls,
                _.tokens,
                attrs_expr,
                _.trace_id,
            )
            .order_by(_.started_at.desc())
            .limit(1)
        )

        result = query.execute()
        if result.empty:
            return None
        return tuple(result.iloc[0])

    def mark_run_completed(
        self,
        *,
        run_id: uuid.UUID,
        finished_at: datetime,
        duration_seconds: float,
        rows_out: int | None,
    ) -> None:
        """Update ``runs`` when a stage completes."""
        runs = self.storage.read_table("runs")
        run_id_literal = ibis.literal(str(run_id))
        match_run = runs.run_id.cast("string") == run_id_literal

        updates: dict[str, object] = {
            "status": ibis.where(match_run, ibis.literal("completed"), runs.status),
            "finished_at": ibis.where(match_run, ibis.literal(finished_at), runs.finished_at),
        }

        if "duration_seconds" in runs.columns:
            updates["duration_seconds"] = ibis.where(
                match_run, ibis.literal(duration_seconds), runs.duration_seconds
            )

        if "rows_out" in runs.columns:
            updates["rows_out"] = ibis.where(match_run, ibis.literal(rows_out), runs.rows_out)

        updated_table = runs.mutate(**updates)
        self.storage.persist_atomic(updated_table, "runs", schema=runs.schema())

    def mark_run_failed(
        self,
        *,
        run_id: uuid.UUID,
        finished_at: datetime,
        duration_seconds: float,
        error: str,
    ) -> None:
        """Update ``runs`` when a stage fails."""
        runs = self.storage.read_table("runs")
        run_id_literal = ibis.literal(str(run_id))
        match_run = runs.run_id.cast("string") == run_id_literal

        updates: dict[str, object] = {
            "status": ibis.where(match_run, ibis.literal("failed"), runs.status),
            "finished_at": ibis.where(match_run, ibis.literal(finished_at), runs.finished_at),
            "error": ibis.where(match_run, ibis.literal(error), runs.error),
        }

        if "duration_seconds" in runs.columns:
            updates["duration_seconds"] = ibis.where(
                match_run, ibis.literal(duration_seconds), runs.duration_seconds
            )

        updated_table = runs.mutate(**updates)
        self.storage.persist_atomic(updated_table, "runs", schema=runs.schema())

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass
