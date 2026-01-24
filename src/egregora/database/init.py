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
from typing import TYPE_CHECKING

from egregora.database.schemas import (
    ANNOTATIONS_SCHEMA,
    MEDIA_SCHEMA,
    STAGING_MESSAGES_SCHEMA,
    TASKS_SCHEMA,
    UNIFIED_SCHEMA,
    create_table_if_not_exists,
    execute_sql,
    get_table_check_constraints,
)

if TYPE_CHECKING:
    from ibis.backends import BaseBackend

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

    conn = backend.con if hasattr(backend, "con") else backend

    from egregora.database.schemas import get_table_foreign_keys

    # 1. Unified Documents Table
    # This creates the table with the full schema if it's missing.
    create_table_if_not_exists(
        conn,
        "documents",
        UNIFIED_SCHEMA,
        check_constraints=get_table_check_constraints("documents"),
        primary_key="id",
    )

    # 2. Tasks Table
    create_table_if_not_exists(
        conn, "tasks", TASKS_SCHEMA, check_constraints=get_table_check_constraints("tasks")
    )

    # 3. Ingestion Staging Table (Ingestion Buffer)
    create_table_if_not_exists(conn, "messages", STAGING_MESSAGES_SCHEMA)

    # 4. Media and Annotations Tables
    create_table_if_not_exists(
        conn, "media", MEDIA_SCHEMA, check_constraints=get_table_check_constraints("media")
    )
    create_table_if_not_exists(
        conn,
        "annotations",
        ANNOTATIONS_SCHEMA,
        check_constraints=get_table_check_constraints("annotations"),
        foreign_keys=get_table_foreign_keys("annotations"),
    )

    # Indexes for messages table (Ingestion performance)
    execute_sql(conn, "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_pk ON messages(event_id)")
    execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
    execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)")
    execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_author ON messages(author_uuid)")

    logger.info("✓ Database tables initialized successfully")


__all__ = ["initialize_database"]
