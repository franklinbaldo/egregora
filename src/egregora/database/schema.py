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
"""

import logging

import duckdb
import ibis
import ibis.expr.datatypes as dt

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

logger = logging.getLogger(__name__)


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

# ============================================================================
# RAG Vector Store Schemas
# ============================================================================

RAG_CHUNKS_SCHEMA = ibis.schema(
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

# ============================================================================
# Annotations Schema
# ============================================================================

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

# ============================================================================
# Ranking (Elo) Schemas
# ============================================================================

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


# ============================================================================
# Helper Functions
# ============================================================================


def create_table_if_not_exists(
    conn,
    table_name: str,
    schema: ibis.Schema,
) -> None:
    """Create a table using Ibis schema if it doesn't already exist.

    Args:
        conn: Ibis connection (DuckDB backend)
        table_name: Name of the table to create
        schema: Ibis schema definition

    Note:
        This uses CREATE TABLE IF NOT EXISTS to safely handle existing tables.
        Primary keys and constraints should be added separately if needed.
    """
    # Check if table exists using Ibis
    if table_name not in conn.list_tables():
        # Create empty table with schema
        empty_table = ibis.memtable([], schema=schema)
        conn.create_table(table_name, empty_table, overwrite=False)


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
    return f'"{identifier.replace('"', '""')}"'


def add_primary_key(conn, table_name: str, column_name: str) -> None:
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
        conn.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT pk_{table_name} PRIMARY KEY ({column_name})")
    except duckdb.Error as e:
        # Constraint may already exist - log and continue
        logger.debug("Could not add primary key to %s.%s: %s", table_name, column_name, e)


def ensure_identity_column(
    conn,
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
    try:
        conn.execute(
            f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET GENERATED {generated} AS IDENTITY"
        )
    except duckdb.Error as e:
        # Identity already configured or column contains incompatible data - log and continue
        logger.debug(
            "Could not set identity on %s.%s (generated=%s): %s",
            table_name, column_name, generated, e
        )


def create_index(conn, table_name: str, index_name: str, column_name: str, index_type: str = "HNSW") -> None:
    """Create an index on a table.

    Args:
        conn: DuckDB connection (raw, not Ibis)
        table_name: Name of the table
        index_name: Name for the index
        column_name: Column to index
        index_type: Type of index (HNSW for vector search, standard otherwise)

    Note:
        For vector columns, use index_type='HNSW' with appropriate metric.
        This must be called on raw DuckDB connection, not Ibis connection.
    """
    try:
        if index_type == "HNSW":
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} "
                f"ON {table_name} USING HNSW ({column_name}) "
                "WITH (metric = 'cosine')"
            )
        else:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})")
    except Exception as e:
        # Index may already exist or column may not support this index type
        logging.getLogger(__name__).debug(f"Could not create index {index_name}: {e}")
