"""Centralized database schema definitions for all DuckDB tables.

All table schemas are defined using Ibis for type safety and consistency.
Use these schemas to create tables via Ibis instead of raw SQL.

This module contains both:
- Persistent schemas: Tables that are stored in DuckDB files
- Ephemeral schemas: In-memory tables for transformations (not persisted)
"""

import logging

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
        "mtime_ns": dt.int64,
        "size": dt.int64,
        "checksum": dt.string,
    }
)

RAG_INDEX_META_SCHEMA = ibis.schema(
    {
        "index_name": dt.string,  # PRIMARY KEY
        "mode": dt.string,  # 'ann' or 'exact'
        "row_count": dt.int64,
        "created_at": dt.timestamp,
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
        conn.execute(
            f"ALTER TABLE {table_name} ADD CONSTRAINT pk_{table_name} PRIMARY KEY ({column_name})"
        )
    except Exception:
        # Constraint may already exist
        pass


def ensure_identity_column(
    conn,
    table_name: str,
    column_name: str,
    *,
    generated: str = "ALWAYS",
) -> None:
    """Ensure a column is configured as an identity column in DuckDB."""

    try:
        conn.execute(
            f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
            f"SET GENERATED {generated} AS IDENTITY"
        )
    except Exception:
        # Identity already configured or column contains incompatible data
        pass


def create_index(
    conn, table_name: str, index_name: str, column_name: str, index_type: str = "HNSW"
) -> None:
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
