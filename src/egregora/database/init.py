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

from egregora.database.ir_schema import (
    AGENT_READ_STATUS_SCHEMA,
    CONTENTS_SCHEMA,
    DOCUMENTS_SCHEMA,
    ENTRY_CONTENTS_SCHEMA,
    create_table_if_not_exists,
)

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)


def initialize_database(backend: BaseBackend) -> None:
    """Initialize all database tables using Ibis schema definitions.

    Creates:
    - documents: Unified entry/document storage
    - contents: Content storage
    - entry_contents: Entry-Content association
    - agent_read_status: Tracking read state for agents

    Args:
        backend: Ibis backend (DuckDB, Postgres, etc.)

    Raises:
        Exception: If table creation fails

    Example:
        >>> import ibis
        >>> backend = ibis.duckdb.connect("pipeline.db")
        >>> initialize_database(backend)
        >>> # All tables now exist and can be used

    """
    logger.info("Initializing database tables...")

    # Get the connection for raw SQL execution
    if hasattr(backend, "con"):
        conn = backend.con
    else:
        conn = backend

    # --- Unified Documents Table ---
    create_table_if_not_exists(conn, "documents", DOCUMENTS_SCHEMA)

    _execute_sql(
        conn,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_pk
        ON documents(id)
    """,
    )

    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_documents_feed
        ON documents(feed_id)
    """,
    )

    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_documents_updated
        ON documents(updated)
    """,
    )

    # --- Contents & Association Tables ---
    create_table_if_not_exists(conn, "contents", CONTENTS_SCHEMA)
    create_table_if_not_exists(conn, "entry_contents", ENTRY_CONTENTS_SCHEMA)

    _execute_sql(
        conn,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_contents_pk
        ON contents(id)
    """,
    )

    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_entry_contents_fk
        ON entry_contents(entry_id)
    """,
    )

    _execute_sql(
        conn,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_entry_contents_version
        ON entry_contents(entry_id, version_id)
    """,
    )

    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_entry_contents_content
        ON entry_contents(content_id)
    """,
    )

    # --- Agent Read Status Table ---
    create_table_if_not_exists(conn, "agent_read_status", AGENT_READ_STATUS_SCHEMA)

    _execute_sql(
        conn,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_read_status_pk
        ON agent_read_status(agent_id, entry_id)
    """,
    )

    logger.info("✓ Database tables initialized successfully")


def _execute_sql(conn: object, sql: str) -> None:
    """Execute raw SQL on a connection or backend.

    Args:
        conn: DuckDB connection or Ibis backend
        sql: SQL statement to execute

    """
    if hasattr(conn, "raw_sql"):
        # Ibis backend
        conn.raw_sql(sql)
    else:
        # Raw DuckDB connection
        conn.execute(sql)


__all__ = ["initialize_database"]
