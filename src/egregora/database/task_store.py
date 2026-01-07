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
from typing import TYPE_CHECKING, Any

import ibis
from ibis import literal as L

from egregora.database.schemas import quote_identifier

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager

logger = logging.getLogger(__name__)


class TaskStore:
    """DuckDB-backed task queue using the unified 'documents' table."""

    def __init__(self, storage: DuckDBStorageManager) -> None:
        """Initialize the task store.

        Args:
            storage: The central DuckDB storage manager.

        """
        self.storage = storage

    def enqueue(self, task_type: str, payload: dict[str, Any], run_id: uuid.UUID | None = None) -> str:
        """Add a new task to the documents table.

        Args:
            task_type: Identifier for the worker (e.g., "generate_banner")
            payload: JSON-serializable dictionary of task arguments
            run_id: UUID of the pipeline run (optional, for lineage)

        Returns:
            The generated task_id as a string.

        """
        task_id = uuid.uuid4()
        now = datetime.now(UTC)

        # Map task data to the UNIFIED_SCHEMA
        # 'content' can store task details or be null if payload is sufficient.
        # 'extensions' will store the main payload and metadata.
        task_doc = {
            "id": str(task_id),
            "doc_type": "task",
            "title": task_type,
            "status": "pending",
            "content": f"Task for {task_type}",
            "created_at": now,
            "source_checksum": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{task_type}-{now.isoformat()}")),
            "extensions": {
                "payload": payload,
                "processed_at": None,
                "run_id": str(run_id) if run_id else None,
            },
        }

        self.storage.ibis_conn.insert("documents", [task_doc])
        logger.debug("Enqueued task %s (%s)", task_id, task_type)
        return str(task_id)

    def fetch_pending(self, task_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch pending tasks from the documents table.

        Args:
            task_type: Optional filter (e.g., "update_profile")
            limit: Maximum number of tasks to retrieve

        Returns:
            List of task document dictionaries, with payload extracted.

        """
        t = self.storage.read_table("documents")
        query = t.filter((t.doc_type == "task") & (t.status == "pending"))

        if task_type:
            query = query.filter(t.title == task_type)

        query = query.order_by(t.created_at).limit(limit)

        results = []
        for doc in query.execute().to_dict(orient="records"):
            extensions = doc.get("extensions") or {}
            if isinstance(extensions, str):
                extensions = json.loads(extensions)

            task_data = {
                "task_id": doc.get("id"),
                "task_type": doc.get("title"),
                "status": doc.get("status"),
                "created_at": doc.get("created_at"),
                "error": doc.get("summary"),
                "payload": extensions.get("payload"),
                "processed_at": extensions.get("processed_at"),
            }
            results.append(task_data)
        return results

    def _update_status(
        self,
        task_id: uuid.UUID | str,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update a task's status and metadata in the documents table."""
        now = datetime.now(UTC)
        table = self.storage.read_table("documents")
        t_id = str(task_id)

        # Use Ibis mutation for safe updates
        # Update status, summary (for error), and extensions.processed_at
        table_name = quote_identifier("documents")

        # Update status and summary directly
        sql_update = f"""
            UPDATE {table_name}
            SET status = ?, summary = ?
            WHERE id = ? AND doc_type = 'task'
        """
        self.storage.execute_sql(sql_update, params=[status, error, t_id])

        # Update the processed_at in the JSON extensions field
        # DuckDB's JSON support is good, but json_set is not always available.
        # We'll read the extensions, update in Python, and write back.
        sql_select = f"""
            SELECT extensions FROM {table_name}
            WHERE id = ? AND doc_type = 'task'
        """
        result = self.storage.execute_sql(sql_select, params=[t_id]).fetchone()
        if result:
            extensions = json.loads(result[0]) if isinstance(result[0], str) else result[0]
            extensions["processed_at"] = now.isoformat()
            sql_update_json = f"""
                UPDATE {table_name}
                SET extensions = ?
                WHERE id = ? AND doc_type = 'task'
            """
            self.storage.execute_sql(sql_update_json, params=[json.dumps(extensions), t_id])

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
