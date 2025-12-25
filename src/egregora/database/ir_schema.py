"""Ibis schemas for intermediate representations (IR) of data.

This module defines the canonical schemas for pipeline data structures
(e.g., messages, conversations) using Ibis data types.

Using Ibis schemas provides:
- Database-agnostic type definitions
- Single source of truth for table structures
- Compatibility with DuckDB, Postgres, etc.
- Foundation for future data validation and quality checks
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import ibis.expr.datatypes as dt
from ibis.expr.schema import Schema

from egregora.database.utils import quote_identifier

if TYPE_CHECKING:
    import duckdb

logger = logging.getLogger(__name__)

# ==============================================================================
# Canonical Schemas
# ==============================================================================

# Intermediate representation for raw messages from any source
# This is the single source of truth for the 'messages' table schema
IR_MESSAGE_SCHEMA = Schema(
    {
        "event_id": dt.UUID,
        "ts": dt.Timestamp(timezone="UTC"),
        "thread_id": dt.UUID,
        "thread_name": dt.String(nullable=True),
        "author_uuid": dt.UUID,
        "author_name": dt.String(nullable=True),
        "text": dt.String(nullable=True),
        "is_reaction": dt.Boolean(nullable=True),
        "reaction_to": dt.UUID(nullable=True),
        "reaction_emoji": dt.String(nullable=True),
        "is_reply": dt.Boolean(nullable=True),
        "reply_to": dt.UUID(nullable=True),
        "is_edit": dt.Boolean(nullable=True),
        "edit_to": dt.UUID(nullable=True),
        "is_deleted": dt.Boolean(nullable=True),
        "deleted_to": dt.UUID(nullable=True),
        "attachments": dt.JSON(nullable=True),
        "mentions": dt.JSON(nullable=True),
        "links": dt.JSON(nullable=True),
        "source_type": dt.String(),
        "source_id": dt.String(),
        "source_metadata": dt.JSON(nullable=True),
        "original_line": dt.String(nullable=True),  # For debugging/PII validation
    }
)


RUNS_SCHEMA = Schema(
    {
        "run_id": dt.UUID,
        "tenant_id": dt.String(nullable=True),
        "stage": dt.String(),
        "status": dt.String(),  # running, completed, failed
        "error": dt.String(nullable=True),
        "parent_run_id": dt.UUID(nullable=True),
        "code_ref": dt.String(nullable=True),  # git sha
        "config_hash": dt.String(nullable=True),
        "started_at": dt.Timestamp(timezone="UTC"),
        "finished_at": dt.Timestamp(timezone="UTC", nullable=True),
        "duration_seconds": dt.Float64(nullable=True),
        "rows_in": dt.Int64(nullable=True),
        "rows_out": dt.Int64(nullable=True),
        "llm_calls": dt.Int64(nullable=True),
        "tokens": dt.Int64(nullable=True),
        "attrs": dt.JSON(nullable=True),  # Flexible key-value attributes
        "trace_id": dt.String(nullable=True),
    }
)

LINEAGE_SCHEMA = Schema(
    {
        "child_run_id": dt.UUID,
        "parent_run_id": dt.UUID,
        "created_at": dt.Timestamp(timezone="UTC"),
    }
)

TASKS_SCHEMA = Schema(
    {
        "task_id": dt.UUID,
        "created_at": dt.Timestamp(timezone="UTC"),
        "scheduled_for": dt.Timestamp(timezone="UTC"),
        "status": dt.String(),
        "task_type": dt.String(),
        "payload": dt.JSON(),
        "result": dt.JSON(nullable=True),
        "error": dt.String(nullable=True),
        "started_at": dt.Timestamp(timezone="UTC", nullable=True),
        "completed_at": dt.Timestamp(timezone="UTC", nullable=True),
        "priority": dt.Int16(),
        "retries": dt.Int16(),
    }
)

# ==============================================================================
# Schema Management Utilities
# ==============================================================================


def create_table_if_not_exists(conn: Any, table_name: str, schema: Schema) -> None:
    """Create a table from an Ibis schema if it doesn't exist.

    Args:
        conn: DuckDB connection or Ibis backend
        table_name: Name of the table to create
        schema: Ibis schema definition

    """
    quoted_name = quote_identifier(table_name)
    columns_sql = ",\n".join(f"  {quote_identifier(k)} {v.to_duckdb()}" for k, v in schema.fields.items())
    create_sql = f"CREATE TABLE IF NOT EXISTS {quoted_name} (\n{columns_sql}\n)"
    _execute_sql(conn, create_sql)
    logger.debug("Ensured table '%s' exists.", table_name)


def ensure_runs_table_exists(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the 'runs' table if it doesn't exist."""
    create_table_if_not_exists(conn, "runs", RUNS_SCHEMA)


def ensure_lineage_table_exists(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the 'lineage' table if it doesn't exist."""
    create_table_if_not_exists(conn, "lineage", LINEAGE_SCHEMA)


def ensure_messages_table_exists(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the 'messages' table and indexes if they don't exist."""
    create_table_if_not_exists(conn, "messages", IR_MESSAGE_SCHEMA)
    _execute_sql(
        conn,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_pk ON messages(event_id)",
    )
    _execute_sql(
        conn,
        "CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)",
    )
    _execute_sql(
        conn,
        "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)",
    )
    _execute_sql(
        conn,
        "CREATE INDEX IF NOT EXISTS idx_messages_author ON messages(author_uuid)",
    )

def _execute_sql(conn: Any, sql: str) -> None:
    """Execute raw SQL on a connection or backend."""
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

__all__ = [
    "IR_MESSAGE_SCHEMA",
    "RUNS_SCHEMA",
    "LINEAGE_SCHEMA",
    "TASKS_SCHEMA",
    "create_table_if_not_exists",
    "ensure_runs_table_exists",
    "ensure_lineage_table_exists",
    "ensure_messages_table_exists",
]
