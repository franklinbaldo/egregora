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
<<<<<<< HEAD
<<<<<<< HEAD
    GIT_COMMITS_SCHEMA,
=======
>>>>>>> origin/pr/2842
=======
>>>>>>> origin/pr/2835
    STAGING_MESSAGES_SCHEMA,
    TASKS_SCHEMA,
    UNIFIED_SCHEMA,
    create_index,
    create_table_if_not_exists,
    get_table_check_constraints,
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

    # Create indexes for documents
    # These are crucial for performance of queries filtering by doc_type (e.g. ContentRepository.list)
    # and looking up by slug (e.g. finding posts).
    create_index(conn, "documents", "idx_documents_type", "doc_type", index_type="Standard")
    create_index(conn, "documents", "idx_documents_slug", "slug", index_type="Standard")
    create_index(conn, "documents", "idx_documents_created", "created_at", index_type="Standard")

    # 2. Tasks Table
    create_table_if_not_exists(
        conn, "tasks", TASKS_SCHEMA, check_constraints=get_table_check_constraints("tasks")
    )

    # 3. Ingestion Staging Table (Ingestion Buffer)
    create_table_if_not_exists(conn, "messages", STAGING_MESSAGES_SCHEMA)

    # 4. Media and Annotations Tables
    # Media table is deprecated and consolidated into 'documents'.
    create_table_if_not_exists(
        conn,
        "annotations",
        ANNOTATIONS_SCHEMA,
        check_constraints=get_table_check_constraints("annotations"),
        foreign_keys=get_table_foreign_keys("annotations"),
    )

    # Indexes for unified documents table (Query performance)
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_documents_slug ON documents(slug)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")

    # Indexes for messages table (Ingestion performance)
    _execute_sql(conn, "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_pk ON messages(event_id)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_author ON messages(author_uuid)")

<<<<<<< HEAD
    # 5. Git History Cache
    create_table_if_not_exists(conn, "git_commits", GIT_COMMITS_SCHEMA)
    # Composite index for "What was the SHA of this path at time T?"
    _execute_sql(
        conn,
        "CREATE INDEX IF NOT EXISTS idx_git_commits_lookup ON git_commits(repo_path, commit_timestamp DESC)",
    )

    logger.info("✓ Database tables initialized successfully")
=======
    logger.info("✓ Database tables and indexes initialized successfully")
>>>>>>> origin/pr/2860


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
