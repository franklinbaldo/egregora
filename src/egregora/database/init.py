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

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)


def initialize_database(backend: BaseBackend) -> None:
    """Initialize all database tables using Ibis schema definitions.

    Creates the ir_messages table with:
    - All columns from IR_MESSAGE_SCHEMA
    - PRIMARY KEY on event_id
    - Indexes on ts, thread_id, author_uuid for query performance

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
    from egregora.database.ir_schema import IR_MESSAGE_SCHEMA, create_table_if_not_exists  # noqa: PLC0415

    logger.info("Initializing database tables...")

    # Get the connection for raw SQL execution
    if hasattr(backend, "con"):
        conn = backend.con
    else:
        conn = backend

    # Create IR messages table using Python schema definition
    create_table_if_not_exists(conn, "ir_messages", IR_MESSAGE_SCHEMA)

    # Add PRIMARY KEY constraint (DuckDB doesn't support ALTER TABLE ADD PRIMARY KEY,
    # so we need to handle this differently - create a unique index instead)
    # Note: DuckDB's CREATE TABLE IF NOT EXISTS won't add constraints to existing tables
    _execute_sql(
        conn,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ir_messages_pk
        ON ir_messages(event_id)
    """,
    )

    # Add indexes for query performance (matching original SQL schema)
    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_ir_messages_ts
        ON ir_messages(ts)
    """,
    )

    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_ir_messages_thread
        ON ir_messages(thread_id)
    """,
    )

    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_ir_messages_author
        ON ir_messages(author_uuid)
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
