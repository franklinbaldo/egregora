"""Database initialization - create all tables at pipeline start.

This module provides simple, explicit database initialization using Ibis schemas.
All tables are created at the beginning of the pipeline, ensuring consistent schema
throughout the entire pipeline execution.

Design principles:
- Python Ibis schemas as single source of truth (no SQL files)
- Initialize once at pipeline start
- No schema conversion/migration during pipeline execution
- Simple and explicit
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from egregora.database.migrations import migrate_documents_table
from egregora.database.schemas import (
    INGESTION_MESSAGE_SCHEMA,
    TASKS_SCHEMA,
    UNIFIED_SCHEMA,
    add_primary_key,
    create_table_if_not_exists,
)

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)


def initialize_database(backend: BaseBackend) -> None:
    """Initialize all database tables using Ibis schema definitions for Pure.

    Creates:
    - documents (Unified Pure table)
    - tasks (Background jobs)
    - messages (Ingestion buffer)

    Args:
        backend: Ibis backend (DuckDB, Postgres, etc.)

    Raises:
        Exception: If table creation fails

    """
    logger.info("Initializing Pure database tables...")

    if hasattr(backend, "con"):
        conn = backend.con
    else:
        conn = backend

    # 1. Pure Unified Documents Table
    # This creates the table with the full schema if it's missing.
    create_table_if_not_exists(conn, "documents", UNIFIED_SCHEMA)

    # 2. Run Pure schema migration to handle tables created with older schemas.
    # The migration script is idempotent and will do nothing if the schema is current.
    migrate_documents_table(conn)

    # 3. Tasks Table
    create_table_if_not_exists(conn, "tasks", TASKS_SCHEMA)

    # 4. Ingestion / Messages Table (Legacy/Ingestion Support)
    create_table_if_not_exists(conn, "messages", INGESTION_MESSAGE_SCHEMA)
    add_primary_key(conn, "documents", "id")
    add_primary_key(conn, "tasks", "task_id")

    # Indexes for messages table (Ingestion performance)
    _execute_sql(conn, "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_pk ON messages(event_id)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_author ON messages(author_uuid)")

    logger.info("✓ Database tables initialized successfully")


def _execute_sql(conn: Any, sql: str) -> None:
    """Execute raw SQL on a connection or backend.

    Args:
        conn: DuckDB connection or Ibis backend
        sql: SQL statement to execute

    """
    raw_conn = conn.con if hasattr(conn, "con") else conn
    if hasattr(raw_conn, "execute"):
        raw_conn.execute(sql)
    else:
        # Fallback for unexpected connection objects
        msg = f"Connection object {type(conn)} does not support execute"
        raise AttributeError(msg)


__all__ = ["initialize_database"]
