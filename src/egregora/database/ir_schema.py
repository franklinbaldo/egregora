"""Centralized database schema definitions for all DuckDB tables.

All table schemas are defined using Ibis for type safety and consistency.
Use these schemas to create tables via Ibis instead of raw SQL.

This module contains both:
- Persistent schemas: Tables that are stored in DuckDB files
- Ephemeral schemas: In-memory tables for transformations (not persisted)

Type Constructor Pattern:
- Lowercase types (dt.string, dt.int64, dt.date) = NOT NULL
- Capitalized constructors (dt.String(nullable=True), dt.Timestamp(timezone=...)) = allow params
This is standard Ibis convention for nullable vs non-nullable types.

Phase 2 Note:
This module consolidates schemas from schema.py, runs_schema.py, and message_schema.py
for improved maintainability and single source of truth.
"""

from __future__ import annotations

import logging
from typing import Any

import duckdb
import ibis
import ibis.expr.datatypes as dt

from egregora.database.sql import SQLManager
from egregora.database.utils import quote_identifier

logger = logging.getLogger(__name__)

# Single, module-level instance of the SQL manager
sql_manager = SQLManager()


# ============================================================================
# Persistent Schemas
# ============================================================================

# ----------------------------------------------------------------------------
# Append-Only Event Log Schemas (V3 Core)
# ----------------------------------------------------------------------------

FEED_FETCHES_SCHEMA = ibis.schema(
    {
        "fetch_id": dt.int64,
        "feed_url": dt.string,
        "atom_id": dt.String(nullable=True),
        "title": dt.String(nullable=True),
        "subtitle": dt.String(nullable=True),
        "rights": dt.String(nullable=True),
        "language": dt.String(nullable=True),
        "updated": dt.Timestamp(timezone="UTC", nullable=True),
        "etag": dt.String(nullable=True),
        "last_modified": dt.String(nullable=True),
        "http_status": dt.Int32(nullable=True),
        "fetched_at": dt.Timestamp(timezone="UTC"),
        "raw_xml": dt.String(nullable=True),
    }
)

ENTRY_VERSIONS_SCHEMA = ibis.schema(
    {
        "version_id": dt.int64,  # Auto-increment or unique ID
        "feed_url": dt.String(nullable=True),  # Feed this entry belongs to
        "atom_id": dt.string,  # Logical ID of the entry (Entry.id)
        "fetch_id": dt.Int64(nullable=True),  # Link to feed_fetches
        "position": dt.Int32(nullable=True),
        # Entry Core Fields
        "title": dt.String(nullable=True),
        "summary": dt.String(nullable=True),
        "content": dt.String(nullable=True),
        "content_type": dt.String(nullable=True),
        "rights": dt.String(nullable=True),
        "published": dt.Timestamp(timezone="UTC", nullable=True),
        "updated": dt.Timestamp(timezone="UTC", nullable=True),
        # JSON Metadata
        "authors": dt.JSON(nullable=True),
        "links": dt.JSON(nullable=True),
        "categories": dt.JSON(nullable=True),
        "source": dt.JSON(nullable=True),
        "in_reply_to": dt.JSON(nullable=True),
        # Egregora-specific
        "doc_type": dt.String(nullable=True),
        "status": dt.String(nullable=True),
        # Event Metadata
        "event_type": dt.string,  # 'seen', 'enriched', 'tombstone'
        "seen_at": dt.Timestamp(timezone="UTC"),
        "raw_xml": dt.String(nullable=True),
    }
)

# ----------------------------------------------------------------------------
# Agent State Schemas
# ----------------------------------------------------------------------------

AGENT_READ_STATUS_SCHEMA = ibis.schema(
    {
        "agent_id": dt.string,
        "feed_id": dt.String(nullable=True),
        "entry_id": dt.string,
        "read_at": dt.Timestamp(timezone="UTC"),
    }
)

# ----------------------------------------------------------------------------
# RAG Vector Store Schemas
# ----------------------------------------------------------------------------
# NOTE: Windows are runtime-only constructs (see pipeline.py Window dataclass).
# They are NOT persisted as database schemas because they depend on dynamic
# runtime config (step_size, step_unit). Changing windowing params would
# invalidate any persisted window data.

RAG_CHUNKS_SCHEMA = ibis.schema(
    {
        "chunk_id": dt.string,
        "document_type": dt.string,
        "document_id": dt.string,
        "source_path": dt.String(nullable=True),  # Absolute path to source file (for change detection)
        "source_mtime_ns": dt.Int64(nullable=True),  # File mtime in nanoseconds (for incremental indexing)
        "post_slug": dt.String(nullable=True),
        "post_title": dt.String(nullable=True),
        "post_date": dt.date(nullable=True),
        "media_uuid": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        "media_path": dt.String(nullable=True),
        "original_filename": dt.String(nullable=True),
        "message_date": dt.Timestamp(timezone="UTC", nullable=True),
        "author_uuid": dt.String(nullable=True),
        "chunk_index": dt.int64,
        "content": dt.string,
        "embedding": dt.Array(dt.float64),
        "tags": dt.Array(dt.string),
        "authors": dt.Array(dt.string),
        "category": dt.String(nullable=True),
    }
)

RAG_CHUNKS_METADATA_SCHEMA = ibis.schema(
    {
        "path": dt.string,  # PRIMARY KEY
        "mtime_ns": dt.int64,  # File modification time (nanoseconds since epoch)
        "size": dt.int64,  # File size in bytes
        # Number of rows in the Parquet file at time of indexing
        # Semantics: Physical row count from Parquet metadata, updated on write
        # Used to detect stale indices when file is re-written with different row count
        "row_count": dt.int64,
        # Optional hash of the Parquet file for integrity checks
        "checksum": dt.String(nullable=True),
    }
)

RAG_INDEX_META_SCHEMA = ibis.schema(
    {
        "index_name": dt.string,  # PRIMARY KEY
        "mode": dt.string,  # 'ann' or 'exact'
        # Number of rows indexed at time of last update
        # Semantics: Logical row count from vector store at indexing time
        # Used to determine whether to use ANN (if row_count >= threshold) or exact search
        "row_count": dt.int64,
        # Threshold after which ANN indexing should be used
        "threshold": dt.int64,
        # Number of lists used by ANN implementations (optional)
        "nlist": dt.int32(nullable=True),
        # Persisted embedding dimensionality for consistency checks
        "embedding_dim": dt.int32(nullable=True),
        # Timestamp when the index was created (preserved for provenance)
        "created_at": dt.timestamp,
        # Timestamp of the last update to the index metadata
        "updated_at": dt.timestamp(nullable=True),
    }
)

RAG_SEARCH_RESULT_SCHEMA = ibis.schema(
    {
        "chunk_id": dt.string,
        "document_type": dt.string,
        "document_id": dt.string,
        "post_slug": dt.String(nullable=True),
        "post_title": dt.String(nullable=True),
        "post_date": dt.date(nullable=True),
        "media_uuid": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        "media_path": dt.String(nullable=True),
        "original_filename": dt.String(nullable=True),
        "message_date": dt.Timestamp(timezone="UTC", nullable=True),
        "author_uuid": dt.String(nullable=True),
        "chunk_index": dt.int64,
        "content": dt.string,
        "tags": dt.Array(dt.string),
        "authors": dt.Array(dt.string),
        "category": dt.String(nullable=True),
        "similarity": dt.float64,
    }
)

# ----------------------------------------------------------------------------
# Annotations Schema
# ----------------------------------------------------------------------------

ANNOTATIONS_SCHEMA = ibis.schema(
    {
        "id": dt.int64,  # PRIMARY KEY
        "parent_id": dt.string,  # NOT NULL - can reference msg_id or annotation_id
        "parent_type": dt.string,  # NOT NULL - 'message' or 'annotation'
        "author": dt.string,
        "commentary": dt.string,
        "created_at": dt.timestamp,
    }
)

# ----------------------------------------------------------------------------
# Ranking (Elo) Schemas
# ----------------------------------------------------------------------------

ELO_RATINGS_SCHEMA = ibis.schema(
    {
        "post_id": dt.string,  # PRIMARY KEY (VARCHAR in DuckDB)
        "elo_global": dt.float64,  # DEFAULT 1500
        "num_comparisons": dt.int64,  # DEFAULT 0
        "last_updated": dt.timestamp,
    }
)

ELO_HISTORY_SCHEMA = ibis.schema(
    {
        "comparison_id": dt.string,  # PRIMARY KEY (VARCHAR in DuckDB)
        "timestamp": dt.timestamp,  # NOT NULL
        "winner_id": dt.string,  # NOT NULL
        "loser_id": dt.string,  # NOT NULL
        "elo_change": dt.float64,  # NOT NULL
        "tie": dt.boolean,  # DEFAULT FALSE
    }
)

# ----------------------------------------------------------------------------
# Runs Table Schema (Pipeline Execution Tracking)
# ----------------------------------------------------------------------------
# This schema tracks pipeline execution metadata for:
# 1. Simple lineage tracking (parent_run_id column)
# 2. Observability (performance metrics, errors)
# 3. Multi-tenant cost attribution (tokens, LLM calls)
#
# Usage Examples:
#   Find failed runs: SELECT * FROM runs WHERE status = 'failed'
#   Average duration: SELECT stage, AVG(duration_seconds) FROM runs GROUP BY stage
#   Build lineage: Use recursive CTE on parent_run_id
#
# Note: This is the SINGLE SOURCE OF TRUTH for the runs table schema.
# Tables are created from this schema via create_table_if_not_exists.
# ----------------------------------------------------------------------------

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
        # Lineage (simplified single-parent model)
        "parent_run_id": dt.UUID(nullable=True),  # Parent run ID for simple lineage tracking
        # Code version tracking
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
        # Extensibility (for storing aggregate metrics like num_windows, total_posts, etc.)
        "attrs": dt.JSON(nullable=True),  # JSON blob for stage-specific metadata
        # Observability (for Priority D.2)
        "trace_id": dt.String(nullable=True),  # OpenTelemetry trace ID
    }
)

# ----------------------------------------------------------------------------
# Tasks Schema (Asynchronous Background Tasks)
# ----------------------------------------------------------------------------
TASKS_SCHEMA = ibis.schema(
    {
        "task_id": dt.UUID,
        "task_type": dt.string,  # "generate_banner", "update_profile", "enrich_media"
        "status": dt.string,  # "pending", "processing", "completed", "failed", "superseded"
        "payload": dt.JSON,  # Arguments for the task
        "created_at": dt.Timestamp(timezone="UTC"),
        "processed_at": dt.Timestamp(timezone="UTC", nullable=True),
        "error": dt.String(nullable=True),
        "run_id": dt.UUID,  # Link back to the pipeline run
    }
)

# ----------------------------------------------------------------------------
# Run Events Table Schema (REMOVED - 2025-11-17)
# ----------------------------------------------------------------------------
# REMOVED: Event-sourced tracking replaced with simpler stateful runs table.
# Rationale: For alpha, single-table model is sufficient. Event sourcing added
# complexity without clear benefits for current use cases.
# See docs/SIMPLIFICATION_PLAN.md for details.

# RUN_EVENTS_SCHEMA - REMOVED

# RUN_EVENTS_TABLE_DDL - REMOVED (2025-11-17)

# ============================================================================
# Helper Functions
# ============================================================================

# ----------------------------------------------------------------------------
# General Schema Utilities
# ----------------------------------------------------------------------------


def create_table_if_not_exists(
    conn: Any, table_name: str, schema: ibis.Schema, *, overwrite: bool = False
) -> None:
    """Create a table using Ibis if it doesn't already exist."""
    if hasattr(conn, "list_tables"):  # More reliable check for Ibis connection
        if table_name not in conn.list_tables() or overwrite:
            conn.create_table(table_name, schema=schema, overwrite=overwrite)
    else:
        # Raw duckdb connection
        if overwrite:
            conn.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")

        columns_sql = ", ".join(
            f"{quote_identifier(name)} {_ibis_to_duckdb_type(dtype)}" for name, dtype in schema.items()
        )

        # If we dropped the table, we must use CREATE TABLE.
        # Otherwise, CREATE TABLE IF NOT EXISTS is safe.
        create_verb = "CREATE TABLE" if overwrite else "CREATE TABLE IF NOT EXISTS"
        create_sql = f"{create_verb} {quote_identifier(table_name)} ({columns_sql})"
        conn.execute(create_sql)


def _ibis_to_duckdb_type(ibis_type: ibis.expr.datatypes.DataType) -> str:
    """Convert Ibis data type to DuckDB SQL type string.

    Args:
        ibis_type: Ibis data type

    Returns:
        DuckDB SQL type string

    """
    # Mapping of predicate method names to DuckDB type strings
    simple_types = {
        "is_timestamp": "TIMESTAMP WITH TIME ZONE",
        "is_date": "DATE",
        "is_string": "VARCHAR",
        "is_int64": "BIGINT",
        "is_int32": "INTEGER",
        "is_float64": "DOUBLE PRECISION",
        "is_boolean": "BOOLEAN",
        "is_binary": "BLOB",
        "is_uuid": "UUID",
        "is_json": "JSON",
    }

    # Ibis dtypes are value objects (not classes) in 9.x, so prefer predicate methods over isinstance.
    for predicate, sql_type in simple_types.items():
        if callable(getattr(ibis_type, predicate, None)) and getattr(ibis_type, predicate)():
            return sql_type

    # Handle nested types
    if callable(getattr(ibis_type, "is_array", None)) and ibis_type.is_array():
        value_type = _ibis_to_duckdb_type(ibis_type.value_type)
        return f"{value_type}[]"

    # Fallback to string representation
    return str(ibis_type).upper()


def add_primary_key(conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> None:
    """Add a primary key constraint to an existing table.

    Args:
        conn: DuckDB connection (raw, not Ibis)
        table_name: Name of the table
        column_name: Column to use as primary key

    Note:
        DuckDB requires ALTER TABLE for primary key constraints.
        This must be called on raw DuckDB connection, not Ibis connection.

    """
    try:
        sql = sql_manager.render(
            "ddl/add_constraints.sql.jinja",
            constraint_type="primary_key",
            table_name=table_name,
            column_name=column_name,
            constraint_name=f"pk_{table_name}",
        )
        conn.execute(sql)
    except duckdb.Error as e:
        # Constraint may already exist - log and continue
        logger.debug("Could not add primary key to %s.%s: %s", table_name, column_name, e)


def ensure_identity_column(
    conn: Any, table_name: str, column_name: str, *, generated: str = "ALWAYS"
) -> None:
    """Ensure a column is configured as an identity column in DuckDB."""
    if generated not in ("ALWAYS", "BY DEFAULT"):
        msg = f"Invalid identity generation mode: {generated!r}"
        raise ValueError(msg)

    try:
        quoted_table = quote_identifier(table_name)
        quoted_column = quote_identifier(column_name)
        sql = f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_column} SET GENERATED {generated} AS IDENTITY"
        if hasattr(conn, "raw_sql"):
            conn.raw_sql(sql)
        else:
            conn.execute(sql)
    except (duckdb.Error, RuntimeError) as e:
        # Identity column setup failure is non-fatal (might already exist or not supported by backend)
        # duckdb.Error is likely, but catching RuntimeError to be safe against different backends
        logger.debug(
            "Could not set identity on %s.%s (generated=%s): %s", table_name, column_name, generated, e
        )


def create_index(
    conn: Any, table_name: str, index_name: str, column_name: str, index_type: str = "HNSW"
) -> None:
    """Create an index on a table.

    Args:
        conn: DuckDB connection (raw, not Ibis)
        table_name: Name of the table
        index_name: Name for the index
        column_name: Column to index
        index_type: Type of index (HNSW for vector search, standard otherwise)

    Note:
        For vector columns, use index_type='HNSW' with cosine metric (optimized for 768-dim embeddings).
        This must be called on raw DuckDB connection, not Ibis connection.
        Uses CREATE INDEX IF NOT EXISTS to handle already-existing indexes.

    """
    sql = sql_manager.render(
        "ddl/create_index.sql.jinja",
        index_name=index_name,
        table_name=table_name,
        column_name=column_name,
        index_type=index_type,
    )
    conn.execute(sql)


# ----------------------------------------------------------------------------
# Runs Table Utilities
# ----------------------------------------------------------------------------


def create_runs_table(conn: Any) -> None:
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
        # Use centralized schema definition
        create_table_if_not_exists(conn, "runs", RUNS_TABLE_SCHEMA)

        # Add primary key manually (Ibis create table doesn't support PKs well on DuckDB yet)
        add_primary_key(conn, "runs", "run_id")

        # Create indexes manually
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_runs_stage ON runs(stage)",
            "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_runs_tenant ON runs(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id)",
        ]
        if hasattr(conn, "raw_sql"):
            for index_sql in indexes:
                conn.raw_sql(index_sql)
        else:
            for index_sql in indexes:
                conn.execute(index_sql)

        logger.info("Created runs table with indexes")
    except Exception as e:
        msg = f"Failed to create runs table: {e}"
        raise RuntimeError(msg) from e


# create_run_events_table - REMOVED (2025-11-17)


def ensure_runs_table_exists(conn: Any) -> None:
    """Ensure runs table exists (idempotent)."""
    try:
        if hasattr(conn, "list_tables"):
            if "runs" not in conn.list_tables():
                create_runs_table(conn)
        else:
            # Raw duckdb connection
            result = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'runs'"
            ).fetchone()
            if result and result[0] == 0:
                create_runs_table(conn)
    except (duckdb.Error, RuntimeError) as e:
        # Table check failed, attempt creation anyway
        logger.warning("Error checking for runs table existence: %s, attempting creation...", e)
        create_runs_table(conn)


def drop_runs_table(conn: Any) -> None:
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
        sql = "DROP TABLE IF EXISTS runs"
        if hasattr(conn, "raw_sql"):
            conn.raw_sql(sql)
        else:
            conn.execute(sql)
        logger.info("Dropped runs table")
    except Exception:
        logger.exception("Failed to drop runs table")
        raise


# ----------------------------------------------------------------------------
# Lineage Table Schema
# ----------------------------------------------------------------------------

LINEAGE_TABLE_DDL = """
CREATE TABLE lineage (
  -- Lineage Relationship (Composite PRIMARY KEY)
  child_run_id   UUID NOT NULL,
    -- Run ID of the downstream/dependent run
  parent_run_id  UUID NOT NULL,
    -- Run ID of the upstream/dependency run

  PRIMARY KEY (child_run_id, parent_run_id),
    -- A child can have multiple parents (e.g., join two tables)
    -- A parent can have multiple children (e.g., privacy → multiple enrichments)

  -- Foreign Key Constraints
  FOREIGN KEY (child_run_id)  REFERENCES runs(run_id),
  FOREIGN KEY (parent_run_id) REFERENCES runs(run_id)
);

-- Indexes for Performance
-- Find all parents of a run (upstream dependencies)
CREATE INDEX idx_lineage_child ON lineage (child_run_id);

-- Find all children of a run (downstream dependents)
CREATE INDEX idx_lineage_parent ON lineage (parent_run_id);
"""


def create_lineage_table(conn: Any) -> None:
    """Create lineage table in DuckDB connection.

    The lineage table tracks data lineage relationships between pipeline runs,
    enabling dependency tracking, impact analysis, and reproducibility.

    Args:
        conn: DuckDB connection

    Raises:
        RuntimeError: If table creation fails

    Example:
        >>> import duckdb
        >>> conn = duckdb.connect(":memory:")
        >>> create_runs_table(conn)  # Must create runs table first
        >>> create_lineage_table(conn)
        >>> result = conn.execute("SELECT COUNT(*) FROM lineage").fetchone()
        >>> assert result[0] == 0  # Table exists but empty

    """
    try:
        if hasattr(conn, "raw_sql"):
            conn.raw_sql(LINEAGE_TABLE_DDL)
        else:
            conn.execute(LINEAGE_TABLE_DDL)
        logger.info("Created lineage table with indexes")
    except Exception as e:
        msg = f"Failed to create lineage table: {e}"
        raise RuntimeError(msg) from e


def ensure_lineage_table_exists(conn: Any) -> None:
    """Ensure lineage table exists (idempotent)."""
    ensure_runs_table_exists(conn)
    try:
        if hasattr(conn, "list_tables"):
            if "lineage" not in conn.list_tables():
                create_lineage_table(conn)
        else:
            # Raw duckdb connection
            result = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'lineage'"
            ).fetchone()
            if result and result[0] == 0:
                create_lineage_table(conn)
    except (duckdb.Error, RuntimeError) as e:
        # Table check failed, attempt creation anyway
        logger.warning("Error checking for lineage table existence: %s, attempting creation...", e)
        create_lineage_table(conn)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Annotations schema
    "ANNOTATIONS_SCHEMA",
    # Agent/Documents schemas
    "AGENT_READ_STATUS_SCHEMA",
    "FEED_FETCHES_SCHEMA",
    "ENTRY_VERSIONS_SCHEMA",
    # Elo schemas
    "ELO_HISTORY_SCHEMA",
    "ELO_RATINGS_SCHEMA",
    # RAG schemas
    "RAG_CHUNKS_METADATA_SCHEMA",
    "RAG_CHUNKS_SCHEMA",
    "RAG_INDEX_META_SCHEMA",
    "RAG_SEARCH_RESULT_SCHEMA",
    # Runs schema
    "RUNS_TABLE_SCHEMA",
    "TASKS_SCHEMA",
    # General utilities
    "add_primary_key",
    "create_index",
    # Runs utilities
    "create_runs_table",
    "create_table_if_not_exists",
    "drop_runs_table",
    "ensure_identity_column",
    # Message schema utilities
    "ensure_runs_table_exists",
    "quote_identifier",
]
