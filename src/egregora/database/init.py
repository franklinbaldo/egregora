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

import ibis

from egregora.database.ir_schema import (
    AGENT_READ_STATUS_SCHEMA,
    ENTRY_VERSIONS_SCHEMA,
    FEED_FETCHES_SCHEMA,
    create_table_if_not_exists,
)

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)


def initialize_database(backend: BaseBackend) -> None:
    """Initialize all database tables using Ibis schema definitions.

    Creates:
    - feed_fetches: Log of feed fetches
    - entry_versions: Append-only log of entry versions
    - agent_read_status: Tracking read state for agents
    - current_feeds: View of latest feed state
    - current_entries: View of latest entry state

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

    # --- Append-Only Event Log Tables ---
    create_table_if_not_exists(conn, "feed_fetches", FEED_FETCHES_SCHEMA)
    create_table_if_not_exists(conn, "entry_versions", ENTRY_VERSIONS_SCHEMA)

    # Indexes for append-only performance
    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_entry_versions_atom_id
        ON entry_versions(atom_id)
    """,
    )
    _execute_sql(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_entry_versions_seen_at
        ON entry_versions(seen_at)
    """,
    )

    # --- Create Views ---
    # We must ensure tables exist before defining views
    _create_current_views(backend)

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


def _create_current_views(backend: BaseBackend) -> None:
    """Create views for current state of feeds and entries."""
    if not hasattr(backend, "create_view"):
        logger.warning("Backend does not support create_view, skipping view creation.")
        return

    try:
        # Need to reconnect/refresh table references to ensure they exist
        feed_fetches = backend.table("feed_fetches")
        entry_versions = backend.table("entry_versions")

        # current_feeds view
        feed_window = ibis.window(
            group_by=[feed_fetches.feed_url],
            order_by=[feed_fetches.fetched_at.desc()],
        )
        current_feeds_expr = (
            feed_fetches.mutate(rn=ibis.row_number().over(feed_window))
            .filter(lambda t: t.rn == 0)
            .drop("rn")
        )
        backend.create_view("current_feeds", current_feeds_expr, overwrite=True)

        # current_entries view
        entry_window = ibis.window(
            group_by=[entry_versions.atom_id],
            order_by=[entry_versions.seen_at.desc()],
        )
        current_entries_expr = (
            entry_versions.mutate(rn=ibis.row_number().over(entry_window))
            .filter(lambda t: (t.rn == 0) & (t.event_type != "tombstone"))
            .drop("rn")
        )
        backend.create_view("current_entries", current_entries_expr, overwrite=True)

        logger.info("✓ Views initialized successfully")

    except Exception as e:
        logger.warning("Failed to create views: %s", e)


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
