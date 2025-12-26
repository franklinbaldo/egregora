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

from egregora.database.schemas import (
    ANNOTATIONS_SCHEMA,
    INGESTION_MESSAGE_SCHEMA,
    TASKS_SCHEMA,
    UNIFIED_SCHEMA,
    create_table_if_not_exists,
)

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)


def initialize_database(backend: BaseBackend) -> None:
    """Initialize all database tables using Ibis schema definitions.

    Creates:
    - documents (V3 unified table)
    - tasks (Background jobs)
    - messages (Ingestion buffer - optional/legacy)
    - annotations (Legacy support)

    Args:
        backend: Ibis backend (DuckDB, Postgres, etc.)

    Raises:
        Exception: If table creation fails

    """
    logger.info("Initializing database tables...")

    # Get the connection for raw SQL execution
    if hasattr(backend, "con"):
        conn = backend.con
    else:
        conn = backend

    # Check if a migration is needed before creating tables.
    # The presence of `posts` is a strong signal of a legacy V2 database.
    # The absence of `documents` confirms the migration hasn't run.
    tables = conn.list_tables()
    if "posts" in tables and "documents" not in tables:
        logger.info("Legacy 'posts' table detected and 'documents' table not found. Running V3 migration...")
        from egregora.database.migrations import migrate_to_unified_schema

        migrate_to_unified_schema(conn)
        logger.info("Migration complete.")

    # 1. V3 Unified Documents Table
    create_table_if_not_exists(conn, "documents", UNIFIED_SCHEMA)

    # 2. Tasks Table
    create_table_if_not_exists(conn, "tasks", TASKS_SCHEMA)

    # 3. Annotations Table (for now)
    create_table_if_not_exists(conn, "annotations", ANNOTATIONS_SCHEMA)

    # 4. Ingestion / Messages Table (Legacy/Ingestion Support)
    create_table_if_not_exists(conn, "messages", INGESTION_MESSAGE_SCHEMA)

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
    if hasattr(conn, "raw_sql"):
        # Ibis backend
        conn.raw_sql(sql)
    elif hasattr(conn, "execute"):
        # Raw DuckDB connection
        conn.execute(sql)
    else:
        # Fallback for unexpected connection objects
        msg = f"Connection object {type(conn)} does not support raw_sql or execute"
        raise AttributeError(msg)


__all__ = ["initialize_database"]
