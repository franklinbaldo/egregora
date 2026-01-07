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
    UNIFIED_SCHEMA,
    create_table_if_not_exists,
)

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)


def initialize_database(backend: BaseBackend) -> None:
    """Initialize all database tables using Ibis schema definitions for V3.

    Creates:
    - documents (Unified V3 table)
    - tasks (Background jobs)
    - messages (Ingestion buffer)

    Args:
        backend: Ibis backend (DuckDB, Postgres, etc.)

    Raises:
        Exception: If table creation fails

    """
    logger.info("Initializing V3 database tables...")

    if hasattr(backend, "con"):
        conn = backend.con
    else:
        conn = backend

    # 1. V3 Unified Documents Table
    # This creates the table with the full schema if it's missing.
    create_table_if_not_exists(conn, "documents", UNIFIED_SCHEMA)

    # 2. Run V3 schema migration to handle tables created with older schemas.
    # The migration script is idempotent and will do nothing if the schema is current.
    migrate_documents_table(conn)

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
