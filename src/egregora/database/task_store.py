"""Persistent task queue for asynchronous pipeline operations.

This module manages background tasks (banners, profiling, enrichment) using
DuckDB as a lightweight persistent queue. It supports task chaining and
coalescing (deduplication) patterns.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.ir_schema import TASKS_SCHEMA, quote_identifier

logger = logging.getLogger(__name__)


class TaskStore:
    """DuckDB-backed task queue for async operations."""

    def __init__(self, storage: DuckDBStorageManager) -> None:
        """Initialize the task store.

        Args:
            storage: The central DuckDB storage manager.

        """
        self.storage = storage
        if "tasks" not in self.storage.list_tables():
            self.storage.ibis_conn.create_table("tasks", schema=TASKS_SCHEMA)

    def enqueue(self, task_type: str, payload: dict[str, Any], run_id: uuid.UUID) -> str:
        """Add a new task to the queue.

        Args:
            task_type: Identifier for the worker (e.g., "generate_banner")
            payload: JSON-serializable dictionary of task arguments
            run_id: UUID of the pipeline run creating this task

        Returns:
            The generated task_id as a string

        """
        task_id = uuid.uuid4()

        # Ibis handles the dict -> JSON conversion for the payload column
        # Converting UUIDs to strings to avoid Arrow serialization issues
        # Explicitly serializing payload to JSON string to avoid PyArrow/DuckDB conversion issues
        row = {
            "task_id": str(task_id),
            "task_type": task_type,
            "status": "pending",
            "payload": json.dumps(payload),
            "created_at": datetime.now(UTC),
            "processed_at": None,
            "error": None,
            "run_id": str(run_id),
        }

        # Pass as a list to ensure it's treated as a row, not scalar values
        self.storage.ibis_conn.insert("tasks", [row])
        logger.debug("Enqueued task %s (%s)", task_id, task_type)
        return str(task_id)

    def fetch_pending(self, task_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch pending tasks, optionally filtered by type.

        Args:
            task_type: Optional filter (e.g., "update_profile")
            limit: Maximum number of tasks to retrieve

        Returns:
            List of task dictionaries (including payload)

        """
        t = self.storage.read_table("tasks")
        query = t.filter(t.status == "pending")

        if task_type:
            query = query.filter(t.task_type == task_type)

        # Order by creation time to ensure FIFO processing
        # (Workers may override this order for optimization, e.g., coalescing)
        query = query.order_by(t.created_at).limit(limit)

        return query.execute().to_dict(orient="records")

    def _update_status(
        self,
        task_id: uuid.UUID | str,
        status: str,
        error: str | None = None,
    ) -> None:
        """Internal helper to update task status using raw SQL."""
        now = datetime.now(UTC)
        table_name = quote_identifier("tasks")

        # Use raw SQL for specific updates to ensure immediate visibility
        sql = f"""
            UPDATE {table_name}
            SET status = ?, processed_at = ?, error = ?
            WHERE task_id = ?
        """
        # Ensure UUID is string for DuckDB binding
        t_id = str(task_id)

        self.storage.execute_sql(sql, params=[status, now, error, t_id])

    def mark_completed(self, task_id: uuid.UUID | str) -> None:
        """Mark a task as successfully completed."""
        self._update_status(task_id, "completed")
        logger.debug("Task %s completed", task_id)

    def mark_failed(self, task_id: uuid.UUID | str, error_message: str) -> None:
        """Mark a task as failed with an error message."""
        self._update_status(task_id, "failed", error=error_message)
        logger.error("Task %s failed: %s", task_id, error_message)

    def mark_superseded(self, task_id: uuid.UUID | str, reason: str = "Newer update found") -> None:
        """Mark task as skipped/superseded by a newer task (Optimization)."""
        self._update_status(task_id, "superseded", error=reason)
        logger.debug("Task %s superseded: %s", task_id, reason)
