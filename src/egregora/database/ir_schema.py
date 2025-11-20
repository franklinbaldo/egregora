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
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import duckdb
import ibis
import ibis.expr.datatypes as dt
from ibis import udf

from egregora.data_primitives import GroupSlug

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)


# ============================================================================
# Ephemeral/In-Memory Schemas (Not Persisted)
# ============================================================================
# These schemas define the structure of data that flows through the pipeline
# but is never persisted to disk (for privacy/performance reasons).
# Having schemas for ephemeral data provides:
# - Type safety during transformations
# - Documentation of data contracts
# - Optimization for vectorized operations
# - Validation capabilities

DEFAULT_TIMEZONE = "UTC"

# Primary conversation schema used throughout the pipeline
CONVERSATION_SCHEMA = ibis.schema(
    {
        "timestamp": dt.Timestamp(timezone="UTC", scale=9),  # nanosecond precision
        "date": dt.date,
        "author": dt.string,  # Anonymized UUID after privacy stage
        "message": dt.string,
        "original_line": dt.string,  # Raw line from WhatsApp export
        "tagged_line": dt.string,  # Processed line with mentions
        "message_id": dt.String(nullable=True),  # milliseconds since first message (group creation)
    }
)

# Alias for CONVERSATION_SCHEMA - represents WhatsApp export data
WHATSAPP_CONVERSATION_SCHEMA = CONVERSATION_SCHEMA

# Message schema as dict (used by message_schema.py utilities)
MESSAGE_SCHEMA: dict[str, dt.DataType] = {
    "timestamp": dt.Timestamp(timezone=DEFAULT_TIMEZONE, scale=9),
    "date": dt.Date(),
    "author": dt.String(),
    "message": dt.String(),
    "original_line": dt.String(),
    "tagged_line": dt.String(),
    "message_id": dt.String(nullable=True),
    "event_id": dt.UUID(nullable=True),
}

# Legacy alias
WHATSAPP_SCHEMA = MESSAGE_SCHEMA

# ============================================================================
# Persistent Schemas
# ============================================================================

# ----------------------------------------------------------------------------
# Interchange Representation (IR) v1 Message Schema
# ----------------------------------------------------------------------------

IR_MESSAGE_SCHEMA = ibis.schema(
    {
        # Identity
        # NOTE: UUID columns stored as dt.string in Ibis, DuckDB schema handles conversion to UUID type
        "event_id": dt.string,
        # Multi-Tenant
        "tenant_id": dt.string,
        "source": dt.string,
        # Threading
        "thread_id": dt.string,
        "msg_id": dt.string,
        # Temporal
        "ts": dt.Timestamp(timezone="UTC"),
        # Authors (PRIVACY BOUNDARY)
        "author_raw": dt.string,
        "author_uuid": dt.string,
        # Content
        "text": dt.String(nullable=True),
        "media_url": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        # Metadata
        "attrs": dt.JSON(nullable=True),
        "pii_flags": dt.JSON(nullable=True),
        # Lineage
        "created_at": dt.Timestamp(timezone="UTC"),
        "created_by_run": dt.string,
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
# The SQL DDL below (RUNS_TABLE_DDL) is used for table creation.
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
# Run Events Table Schema (REMOVED - 2025-11-17)
# ----------------------------------------------------------------------------
# REMOVED: Event-sourced tracking replaced with simpler stateful runs table.
# Rationale: For alpha, single-table model is sufficient. Event sourcing added
# complexity without clear benefits for current use cases.
# See docs/SIMPLIFICATION_PLAN.md for details.

# RUN_EVENTS_SCHEMA - REMOVED

RUNS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id UUID PRIMARY KEY,
    tenant_id VARCHAR,
    stage VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'degraded')),
    error TEXT,
    parent_run_id UUID,
    code_ref VARCHAR,
    config_hash VARCHAR,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE,
    rows_in BIGINT,
    rows_out BIGINT,
    duration_seconds DOUBLE PRECISION,
    llm_calls BIGINT,
    tokens BIGINT,
    attrs JSON,
    trace_id VARCHAR
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_stage ON runs(stage);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_tenant ON runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id);
"""

# RUN_EVENTS_TABLE_DDL - REMOVED (2025-11-17)

# ============================================================================
# Helper Functions
# ============================================================================

# ----------------------------------------------------------------------------
# General Schema Utilities
# ----------------------------------------------------------------------------


def create_table_if_not_exists(
    conn: duckdb.DuckDBPyConnection | Any,  # Any allows Ibis DuckDBBackend
    table_name: str,
    schema: ibis.Schema,
) -> None:
    """Create a table using Ibis schema if it doesn't already exist.

    Args:
        conn: DuckDB connection or Ibis DuckDB backend
        table_name: Name of the table to create
        schema: Ibis schema definition

    Note:
        This uses CREATE TABLE IF NOT EXISTS to safely handle existing tables.
        Primary keys and constraints should be added separately if needed.
        Accepts both raw DuckDB connections and Ibis backends.

    """
    # Convert Ibis schema to DuckDB SQL column definitions
    column_defs = []
    for name, dtype in schema.items():
        # Map Ibis types to DuckDB types
        sql_type = _ibis_to_duckdb_type(dtype)
        column_defs.append(f"{quote_identifier(name)} {sql_type}")

    columns_sql = ", ".join(column_defs)
    create_sql = f"CREATE TABLE IF NOT EXISTS {quote_identifier(table_name)} ({columns_sql})"

    # Check if this is an Ibis backend or raw DuckDB connection
    if hasattr(conn, "raw_sql"):
        # Ibis backend - use raw_sql for SQL strings
        conn.raw_sql(create_sql)
    else:
        # Raw DuckDB connection - use execute
        conn.execute(create_sql)


def _ibis_to_duckdb_type(ibis_type: ibis.expr.datatypes.DataType) -> str:
    """Convert Ibis data type to DuckDB SQL type string.

    Args:
        ibis_type: Ibis data type

    Returns:
        DuckDB SQL type string

    """
    import ibis.expr.datatypes as dt

    if isinstance(ibis_type, dt.Timestamp):
        return "TIMESTAMP WITH TIME ZONE"
    if isinstance(ibis_type, dt.Date):
        return "DATE"
    if isinstance(ibis_type, dt.String):
        return "VARCHAR"
    if isinstance(ibis_type, dt.Int64):
        return "BIGINT"
    if isinstance(ibis_type, dt.Int32):
        return "INTEGER"
    if isinstance(ibis_type, dt.Float64):
        return "DOUBLE PRECISION"
    if isinstance(ibis_type, dt.Boolean):
        return "BOOLEAN"
    if isinstance(ibis_type, dt.Binary):
        return "BLOB"
    if isinstance(ibis_type, dt.UUID):
        return "UUID"
    # Fallback to string representation
    return str(ibis_type).upper()


def quote_identifier(identifier: str) -> str:
    """Quote a SQL identifier to prevent injection and handle special characters.

    Args:
        identifier: The identifier to quote (table name, column name, etc.)

    Returns:
        Properly quoted identifier safe for use in SQL

    Note:
        DuckDB uses double quotes for identifiers. Inner quotes are escaped by doubling.
        Example: my"table → "my""table"

    """
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


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
        # Use quoted identifiers to prevent SQL injection
        quoted_table = quote_identifier(table_name)
        quoted_column = quote_identifier(column_name)
        constraint_name = quote_identifier(f"pk_{table_name}")
        conn.execute(
            f"ALTER TABLE {quoted_table} ADD CONSTRAINT {constraint_name} PRIMARY KEY ({quoted_column})"
        )
    except duckdb.Error as e:
        # Constraint may already exist - log and continue
        logger.debug("Could not add primary key to %s.%s: %s", table_name, column_name, e)


def ensure_identity_column(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
    *,
    generated: str = "ALWAYS",
) -> None:
    """Ensure a column is configured as an identity column in DuckDB.

    Args:
        conn: DuckDB connection (raw, not Ibis)
        table_name: Name of the table
        column_name: Column to configure as identity
        generated: 'ALWAYS' or 'BY DEFAULT' for identity generation

    Note:
        This must be called on raw DuckDB connection, not Ibis connection.
        If the column already has identity configured, this is a no-op.

    """
    # Validate generated parameter to prevent SQL injection
    if generated not in ("ALWAYS", "BY DEFAULT"):
        msg = f"Invalid identity generation mode: {generated!r}. Must be 'ALWAYS' or 'BY DEFAULT'."
        raise ValueError(msg)

    try:
        # Use quoted identifiers to prevent SQL injection
        quoted_table = quote_identifier(table_name)
        quoted_column = quote_identifier(column_name)
        # generated is validated above, safe to interpolate
        conn.execute(
            f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_column} SET GENERATED {generated} AS IDENTITY"
        )
    except duckdb.Error as e:
        # Identity already configured or column contains incompatible data - log and continue
        logger.debug(
            "Could not set identity on %s.%s (generated=%s): %s", table_name, column_name, generated, e
        )


def create_index(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    index_name: str,
    column_name: str,
    index_type: str = "HNSW",
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
    # Use quoted identifiers to prevent SQL injection
    quoted_index = quote_identifier(index_name)
    quoted_table = quote_identifier(table_name)
    quoted_column = quote_identifier(column_name)

    if index_type == "HNSW":
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {quoted_index} "
            f"ON {quoted_table} USING HNSW ({quoted_column}) "
            "WITH (metric = 'cosine')"
        )
    else:
        conn.execute(f"CREATE INDEX IF NOT EXISTS {quoted_index} ON {quoted_table} ({quoted_column})")


# ----------------------------------------------------------------------------
# Runs Table Utilities
# ----------------------------------------------------------------------------


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


# create_run_events_table - REMOVED (2025-11-17)


def ensure_runs_table_exists(conn: duckdb.DuckDBPyConnection) -> None:
    """Ensure runs table exists (idempotent).

    This is the recommended function to call before any runs operations.
    It will create the table if it doesn't exist, or do nothing if it does.

    Args:
        conn: DuckDB connection

    Example:
        >>> from egregora.database import DuckDBStorageManager
        >>> storage = DuckDBStorageManager()
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
    except duckdb.Error as e:
        # If check fails, try creating anyway (DuckDB will skip if exists)
        logger.warning("Error checking for runs table existence: %s, attempting creation...", e)
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


def create_lineage_table(conn: duckdb.DuckDBPyConnection) -> None:
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
        conn.execute(LINEAGE_TABLE_DDL)
        logger.info("Created lineage table with indexes")
    except Exception as e:
        msg = f"Failed to create lineage table: {e}"
        raise RuntimeError(msg) from e


def ensure_lineage_table_exists(conn: duckdb.DuckDBPyConnection) -> None:
    """Ensure lineage table exists (idempotent).

    This is the recommended function to call before any lineage operations.
    It will create the table if it doesn't exist, or do nothing if it does.

    Note: This function also ensures the runs table exists, since lineage
    has foreign key constraints to the runs table.

    Args:
        conn: DuckDB connection

    Example:
        >>> from egregora.database import DuckDBStorageManager
        >>> storage = DuckDBStorageManager()
        >>> ensure_lineage_table_exists(storage.conn)  # Safe to call multiple times

    """
    # Ensure runs table exists first (lineage has FK to runs)
    ensure_runs_table_exists(conn)

    try:
        # Check if table exists
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'lineage'"
        ).fetchone()

        if result and result[0] == 0:
            logger.debug("Lineage table doesn't exist, creating...")
            create_lineage_table(conn)
        else:
            logger.debug("Lineage table already exists")
    except duckdb.Error as e:
        # If check fails, try creating anyway (DuckDB will skip if exists)
        logger.warning("Error checking for lineage table existence: %s, attempting creation...", e)
        create_lineage_table(conn)


def drop_lineage_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Drop lineage table (for testing/cleanup).

    Args:
        conn: DuckDB connection

    Warning:
        This permanently deletes all lineage history!

    Example:
        >>> import duckdb
        >>> conn = duckdb.connect(":memory:")
        >>> create_lineage_table(conn)
        >>> drop_lineage_table(conn)

    """
    try:
        conn.execute("DROP TABLE IF EXISTS lineage")
        logger.info("Dropped lineage table")
    except Exception:
        logger.exception("Failed to drop lineage table")
        raise


# ----------------------------------------------------------------------------
# Message Schema Utilities
# ----------------------------------------------------------------------------


def group_slug(group_name: str) -> GroupSlug:
    """Create a URL-safe slug from a group name.

    Args:
        group_name: The display name of the group

    Returns:
        A URL-safe slug suitable for use in file paths and URLs

    """
    return GroupSlug(group_name.lower().replace(" ", "-"))


@udf.scalar.builtin(
    name="timezone", signature=((dt.string, dt.Timestamp(timezone=None)), dt.Timestamp(timezone="UTC"))
)
def _builtin_timezone(_: str, __: dt.Timestamp) -> dt.Timestamp:
    """Bind to backend ``timezone`` scalar function.

    The function body is never executed; at runtime Ibis forwards calls to the
    backend implementation. DuckDB mirrors Polars' ``replace_time_zone``
    semantics when a naive timestamp is paired with the export's timezone.
    """


def ensure_message_schema(table: Table, *, timezone: str | ZoneInfo | None = None) -> Table:
    """Return ``table`` cast to the canonical :data:`MESSAGE_SCHEMA`.

    The pipeline relies on consistent dtypes so schema validation is performed
    eagerly at ingestion boundaries (parser and render stages). This function
    strictly enforces MESSAGE_SCHEMA by:
    - Adding missing columns with nulls
    - Casting existing columns to correct types
    - Dropping any extra columns not in MESSAGE_SCHEMA
    - Normalizing timezone information
    """
    target_schema = dict(MESSAGE_SCHEMA)
    tz = timezone or DEFAULT_TIMEZONE
    tz_name = getattr(tz, "key", str(tz)) if isinstance(tz, ZoneInfo) else str(tz)
    target_schema["timestamp"] = dt.Timestamp(timezone=tz_name, scale=9)
    if int(table.count().execute()) == 0:
        return ibis.memtable([], schema=ibis.schema(target_schema))
    result = table
    for name, dtype in target_schema.items():
        if name in {"timestamp", "date"}:
            continue
        if name in result.columns:
            result = result.mutate(**{name: result[name].cast(dtype)})
        else:
            result = result.mutate(**{name: ibis.null().cast(dtype)})
    if "timestamp" not in result.columns:
        msg = "Table is missing required 'timestamp' column"
        raise ValueError(msg)
    result = _normalise_timestamp(result, tz_name)
    result = _ensure_date_column(result)
    extra_columns = set(result.columns) - set(target_schema.keys())
    if extra_columns:
        result = result.select(*target_schema.keys())
    return result


def _normalise_timestamp(table: Table, desired_timezone: str) -> Table:
    """Normalize timestamp column to desired timezone."""
    schema = table.schema()
    current_dtype = schema.get("timestamp")
    if current_dtype is None:
        msg = "Table is missing required 'timestamp' column"
        raise ValueError(msg)
    desired_dtype = dt.Timestamp(timezone=desired_timezone, scale=9)
    ts_col = table["timestamp"]
    current_timezone: str | None
    if isinstance(current_dtype, dt.Timestamp):
        current_timezone = current_dtype.timezone
        if current_dtype.scale != desired_dtype.scale:
            ts_col = ts_col.cast(dt.Timestamp(timezone=current_timezone, scale=desired_dtype.scale))
    else:
        ts_col = ts_col.cast(dt.Timestamp(scale=desired_dtype.scale))
        current_timezone = None
    if desired_timezone is None:
        normalized_ts = ts_col
    elif current_timezone is None:
        localized = _builtin_timezone(desired_timezone, ts_col.cast(dt.Timestamp()))
        normalized_ts = localized.cast(desired_dtype)
    elif current_timezone == desired_timezone:
        normalized_ts = ts_col
    else:
        normalized_ts = ts_col.cast(desired_dtype)
    return table.mutate(timestamp=normalized_ts)


def _ensure_date_column(table: Table) -> Table:
    """Ensure date column exists, deriving from timestamp if needed."""
    if "date" in table.columns:
        return table.mutate(date=table["date"].cast(dt.Date()))
    return table.mutate(date=table["timestamp"].date())


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Annotations schema
    "ANNOTATIONS_SCHEMA",
    # Ephemeral schemas
    "CONVERSATION_SCHEMA",
    "DEFAULT_TIMEZONE",
    # Elo schemas
    "ELO_HISTORY_SCHEMA",
    "ELO_RATINGS_SCHEMA",
    "IR_MESSAGE_SCHEMA",
    "MESSAGE_SCHEMA",
    # RAG schemas
    "RAG_CHUNKS_METADATA_SCHEMA",
    "RAG_CHUNKS_SCHEMA",
    "RAG_INDEX_META_SCHEMA",
    "RAG_SEARCH_RESULT_SCHEMA",
    # Runs schema
    "RUNS_TABLE_DDL",
    "RUNS_TABLE_SCHEMA",
    "WHATSAPP_CONVERSATION_SCHEMA",
    "WHATSAPP_SCHEMA",
    # General utilities
    "add_primary_key",
    "create_index",
    # Runs utilities
    "create_runs_table",
    "create_table_if_not_exists",
    "drop_runs_table",
    "ensure_identity_column",
    # Message schema utilities
    "ensure_message_schema",
    "ensure_runs_table_exists",
    "group_slug",
    "quote_identifier",
]
