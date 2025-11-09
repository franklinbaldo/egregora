"""Runs table schema for pipeline execution tracking.

This module defines the schema for tracking pipeline stage executions,
enabling observability, debugging, and lineage tracking.

Usage:
    from egregora.database.runs_schema import (
        RUNS_TABLE_SCHEMA,
        create_runs_table,
        ensure_runs_table_exists,
    )

    # Create runs table
    storage = StorageManager()
    create_runs_table(storage.conn)

    # Or ensure it exists (idempotent)
    ensure_runs_table_exists(storage.conn)

See Also:
    - src/egregora/pipeline/runner.py - Stage execution wrapper
    - TODO.md - Priority D.1 implementation plan
    - ARCHITECTURE_ROADMAP.md:1016-1168 - D.1 specification

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import ibis
import ibis.expr.datatypes as dt

if TYPE_CHECKING:
    import duckdb

logger = logging.getLogger(__name__)

__all__ = [
    "RUNS_TABLE_DDL",
    "RUNS_TABLE_SCHEMA",
    "create_runs_table",
    "ensure_runs_table_exists",
]

# ============================================================================
# Schema Definition
# ============================================================================

RUNS_TABLE_SCHEMA = ibis.schema(
    {
        # Identity
        "run_id": dt.UUID,
        # Multi-tenant isolation
        "tenant_id": dt.String(nullable=True),  # Tenant identifier (multi-tenant isolation)
        # Execution metadata
        "stage": dt.string,  # Stage name (e.g., "parsing", "enrichment", "writing")
        "status": dt.string,  # "running", "completed", "failed"
        "error": dt.String(nullable=True),  # Error message if status="failed"
        # Fingerprinting (content-addressed checkpointing)
        "input_fingerprint": dt.String(nullable=True),  # SHA256 of input data + config + code
        "code_ref": dt.String(nullable=True),  # Git commit SHA
        "config_hash": dt.String(nullable=True),  # SHA256 of config
        # Timing
        "started_at": dt.Timestamp(timezone="UTC"),
        "finished_at": dt.Timestamp(timezone="UTC", nullable=True),
        # Metrics
        "rows_in": dt.Int64(nullable=True),
        "rows_out": dt.Int64(nullable=True),
        "duration_seconds": dt.Float64(nullable=True),
        "llm_calls": dt.Int64(nullable=True),
        "tokens": dt.Int64(nullable=True),
        # Observability (for Priority D.2)
        "trace_id": dt.String(nullable=True),  # OpenTelemetry trace ID
    }
)

# ============================================================================
# SQL DDL
# ============================================================================

RUNS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id UUID PRIMARY KEY,
    tenant_id VARCHAR,
    stage VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'degraded')),
    error TEXT,
    input_fingerprint VARCHAR,
    code_ref VARCHAR,
    config_hash VARCHAR,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE,
    rows_in BIGINT,
    rows_out BIGINT,
    duration_seconds DOUBLE PRECISION,
    llm_calls BIGINT,
    tokens BIGINT,
    trace_id VARCHAR
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_stage ON runs(stage);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_fingerprint ON runs(input_fingerprint);
CREATE INDEX IF NOT EXISTS idx_runs_tenant ON runs(tenant_id);
"""

# ============================================================================
# Helper Functions
# ============================================================================


def create_runs_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create runs table in DuckDB connection.

    Args:
        conn: DuckDB connection

    Raises:
        RuntimeError: If table creation fails

    Example:
        >>> import duckdb
        >>> conn = duckdb.connect(":memory:")
        >>> create_runs_table(conn)
        >>> result = conn.execute("SELECT COUNT(*) FROM runs").fetchone()
        >>> assert result[0] == 0  # Table exists but empty

    """
    try:
        conn.execute(RUNS_TABLE_DDL)
        logger.info("Created runs table with indexes")
    except Exception as e:
        msg = f"Failed to create runs table: {e}"
        raise RuntimeError(msg) from e


def ensure_runs_table_exists(conn: duckdb.DuckDBPyConnection) -> None:
    """Ensure runs table exists (idempotent).

    This is the recommended function to call before any runs operations.
    It will create the table if it doesn't exist, or do nothing if it does.

    Args:
        conn: DuckDB connection

    Example:
        >>> from egregora.database import StorageManager
        >>> storage = StorageManager()
        >>> ensure_runs_table_exists(storage.conn)  # Safe to call multiple times

    """
    try:
        # Check if table exists
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
        ).fetchone()

        if result and result[0] == 0:
            logger.debug("Runs table doesn't exist, creating...")
            create_runs_table(conn)
        else:
            logger.debug("Runs table already exists")
    except Exception as e:
        # If check fails, try creating anyway (DuckDB will skip if exists)
        logger.warning(f"Error checking for runs table existence: {e}, attempting creation...")
        create_runs_table(conn)


def drop_runs_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Drop runs table (for testing/cleanup).

    Args:
        conn: DuckDB connection

    Warning:
        This permanently deletes all run history!

    Example:
        >>> import duckdb
        >>> conn = duckdb.connect(":memory:")
        >>> create_runs_table(conn)
        >>> drop_runs_table(conn)

    """
    try:
        conn.execute("DROP TABLE IF EXISTS runs")
        logger.info("Dropped runs table")
    except Exception as e:
        logger.error(f"Failed to drop runs table: {e}")
        raise
