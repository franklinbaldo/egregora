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
    ASSET_CACHE_SCHEMA,
    ELO_HISTORY_SCHEMA,
    ELO_RATINGS_SCHEMA,
    GIT_COMMITS_SCHEMA,
    GIT_REFS_SCHEMA,
    STAGING_MESSAGES_SCHEMA,
    TASKS_SCHEMA,
    UNIFIED_SCHEMA,
    add_primary_key,
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
    # Ensure PK exists even if table existed before (Idempotent)
    add_primary_key(conn, "documents", "id")

    # Create indexes for documents
    # These are crucial for performance of queries filtering by doc_type (e.g. ContentRepository.list)
    # and looking up by slug (e.g. finding posts).
    create_index(conn, "documents", "idx_documents_type", "doc_type", index_type="Standard")
    create_index(conn, "documents", "idx_documents_slug", "slug", index_type="Standard")
    create_index(conn, "documents", "idx_documents_created", "created_at", index_type="Standard")
    create_index(conn, "documents", "idx_documents_status", "status", index_type="Standard")

    # 2. Tasks Table
    create_table_if_not_exists(
        conn,
        "tasks",
        TASKS_SCHEMA,
        check_constraints=get_table_check_constraints("tasks"),
        primary_key="task_id",
    )
    add_primary_key(conn, "tasks", "task_id")

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

    # Indexes for messages table (Ingestion performance)
    _execute_sql(conn, "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_pk ON messages(event_id)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)")
    _execute_sql(conn, "CREATE INDEX IF NOT EXISTS idx_messages_author ON messages(author_uuid)")

    # 5. Git History Cache
    create_table_if_not_exists(conn, "git_commits", GIT_COMMITS_SCHEMA, primary_key=["commit_sha", "repo_path"])
    add_primary_key(conn, "git_commits", ["commit_sha", "repo_path"])

    # Manual Migration: Ensure new columns exist for existing tables (Schema Evolution)
    try:
        _execute_sql(conn, "ALTER TABLE git_commits ADD COLUMN IF NOT EXISTS change_type VARCHAR")
        _execute_sql(conn, "ALTER TABLE git_commits ADD COLUMN IF NOT EXISTS stats JSON")
    except Exception as e:
        # Note: If table was just created, columns exist.
        # DuckDB 'ADD COLUMN IF NOT EXISTS' is safe.
        # If backend doesn't support this syntax, it might fail, so we log debug.
        logger.debug("Schema evolution for git_commits (add columns) failed or skipped: %s", e)

    # Composite index for "What was the SHA of this path at time T?"
    _execute_sql(
        conn,
        "CREATE INDEX IF NOT EXISTS idx_git_commits_lookup ON git_commits(repo_path, commit_timestamp DESC)",
    )

    # 6. Git Refs Cache
    create_table_if_not_exists(conn, "git_refs", GIT_REFS_SCHEMA, primary_key="ref_name")
    add_primary_key(conn, "git_refs", "ref_name")
    create_index(conn, "git_refs", "idx_git_refs_name", "ref_name", index_type="Standard")
    create_index(conn, "git_refs", "idx_git_refs_sha", "commit_sha", index_type="Standard")

    # 7. Elo Ratings & History
    create_table_if_not_exists(conn, "elo_ratings", ELO_RATINGS_SCHEMA, primary_key="post_slug")
    add_primary_key(conn, "elo_ratings", "post_slug")
    create_index(conn, "elo_ratings", "idx_elo_ratings_slug", "post_slug", index_type="Standard")

    create_table_if_not_exists(
        conn, "comparison_history", ELO_HISTORY_SCHEMA, primary_key="comparison_id"
    )
    add_primary_key(conn, "comparison_history", "comparison_id")
    create_index(conn, "comparison_history", "idx_comparison_history_ts", "timestamp", index_type="Standard")
    create_index(
        conn,
        "comparison_history",
        "idx_comparison_history_post_a",
        "post_a_slug",
        index_type="Standard",
    )
    create_index(
        conn,
        "comparison_history",
        "idx_comparison_history_post_b",
        "post_b_slug",
        index_type="Standard",
    )

    # 8. Asset Cache
    create_table_if_not_exists(conn, "asset_cache", ASSET_CACHE_SCHEMA, primary_key="url")
    add_primary_key(conn, "asset_cache", "url")
    create_index(conn, "asset_cache", "idx_asset_cache_url", "url", index_type="Standard")
    create_index(conn, "asset_cache", "idx_asset_cache_hash", "content_hash", index_type="Standard")

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
