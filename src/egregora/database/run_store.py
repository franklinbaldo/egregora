"""Data access layer for pipeline run history."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager


class RunStore:
    def __init__(self, storage: DuckDBStorageManager):
        self.storage = storage

    def get_latest_runs(self, n: int = 10):
        """Fetches the last N runs from the database."""
        return self.storage.fetch_latest_runs(limit=n)

    def get_run_by_id(self, run_id: str):
        """Fetches a single run by its full or partial UUID."""
        return self.storage.fetch_run_by_partial_id(run_id)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
