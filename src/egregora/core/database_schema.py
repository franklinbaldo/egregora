"""Centralized database schema definitions for all DuckDB tables.

All table schemas are defined using Ibis for type safety and consistency.
Use these schemas to create tables via Ibis instead of raw SQL.

This module contains both:
- Persistent schemas: Tables that are stored in DuckDB files
- Ephemeral schemas: In-memory tables for transformations (not persisted)

Pipeline Stage Pattern:
- Each pipeline stage (ingestion, privacy, augmentation, knowledge, generation)
  can be represented as an Ibis view or materialized table
- Stages have explicit inputs/outputs defined by schemas
- Use create_stage_view() to define declarative transformations
"""

import logging
from enum import Enum

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
        "games_played": dt.int64,  # DEFAULT 0
        "last_updated": dt.timestamp,  # NOT NULL
    }
)

ELO_HISTORY_SCHEMA = ibis.schema(
    {
        "comparison_id": dt.string,  # PRIMARY KEY (VARCHAR in DuckDB)
        "timestamp": dt.timestamp,  # NOT NULL
        "profile_id": dt.string,  # NOT NULL - User who made the comparison
        "post_a": dt.string,  # NOT NULL - First post being compared
        "post_b": dt.string,  # NOT NULL - Second post being compared
        "winner": dt.string,  # NOT NULL - 'A' or 'B'
        "comment_a": dt.string,  # NOT NULL - LLM comment for post A
        "stars_a": dt.int64,  # NOT NULL - Star rating for post A (1-5)
        "comment_b": dt.string,  # NOT NULL - LLM comment for post B
        "stars_b": dt.int64,  # NOT NULL - Star rating for post B (1-5)
    }
)

# ============================================================================
# Media Files Schema
# ============================================================================

MEDIA_FILES_SCHEMA = ibis.schema(
    {
        "media_id": dt.string,  # PRIMARY KEY - Deterministic hash of original path + timestamp
        "message_timestamp": dt.Timestamp(timezone="UTC", scale=9),  # Link to conversation
        "original_filename": dt.string,  # Original filename from WhatsApp export
        "site_relative_path": dt.string,  # Path relative to site root (e.g., "assets/media/abc123.jpg")
        "description": dt.String(nullable=True),  # LLM-generated description
        "media_type": dt.String(nullable=True),  # MIME type or category (image, video, audio, document)
        "pii_redacted": dt.boolean,  # Whether PII placeholder was applied
    }
)

# ============================================================================
# Pipeline Stage Definitions
# ============================================================================


class PipelineStage(str, Enum):
    """
    Pipeline stages that can be materialized as views or tables.

    Each stage represents a transformation step with well-defined
    inputs and outputs conforming to schemas.
    """

    INGESTED = "ingested_messages"  # Raw parsed data (CONVERSATION_SCHEMA)
    ANONYMIZED = "anonymized_messages"  # Post-privacy (CONVERSATION_SCHEMA with UUIDs)
    ENRICHED = "enriched_messages"  # Post-augmentation (CONVERSATION_SCHEMA + enrichments)
    KNOWLEDGE = "knowledge_context"  # Post-RAG retrieval (context for generation)


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


# ============================================================================
# Pipeline Stage View Helpers
# ============================================================================


def create_stage_view(
    conn,
    stage: PipelineStage,
    source_table,
    *,
    overwrite: bool = True,
) -> None:
    """
    Create or replace a pipeline stage view.

    Views provide a declarative way to define pipeline transformations.
    They are computed on-demand and don't consume storage.

    Args:
        conn: Ibis connection
        stage: Pipeline stage enum value
        source_table: Ibis table expression defining the view
        overwrite: Whether to replace existing view (default: True)

    Example:
        >>> conn = ibis.duckdb.connect("pipeline.duckdb")
        >>> anonymized = conversations.mutate(author=anonymize_udf(conversations.author))
        >>> create_stage_view(conn, PipelineStage.ANONYMIZED, anonymized)
    """
    conn.create_view(stage.value, source_table, overwrite=overwrite)
    logging.getLogger(__name__).info(f"Created view: {stage.value}")


def materialize_stage(
    conn,
    stage: PipelineStage,
    source_table,
    *,
    overwrite: bool = True,
) -> None:
    """
    Materialize a pipeline stage as a table (not a view).

    Use for expensive transformations that shouldn't be recomputed each time.
    Examples: enrichment (LLM calls), embeddings, complex joins.

    Args:
        conn: Ibis connection
        stage: Pipeline stage enum value
        source_table: Ibis table expression to materialize
        overwrite: Whether to replace existing table (default: True)

    Example:
        >>> conn = ibis.duckdb.connect("pipeline.duckdb")
        >>> enriched = enrich_conversations(anonymized)  # Expensive LLM calls
        >>> materialize_stage(conn, PipelineStage.ENRICHED, enriched)
    """
    conn.create_table(stage.value, source_table, overwrite=overwrite)
    logging.getLogger(__name__).info(f"Materialized table: {stage.value}")


def stage_exists(conn, stage: PipelineStage) -> bool:
    """
    Check if a pipeline stage view or table exists.

    Args:
        conn: Ibis connection
        stage: Pipeline stage enum value

    Returns:
        True if stage exists as view or table, False otherwise
    """
    return stage.value in conn.list_tables()
