"""Database schema definitions for Egregora V2 (Clean Break).

This module defines the strictly typed, append-only tables for the new architecture.
"""

from __future__ import annotations

import logging
from typing import Any

import duckdb
import ibis
import ibis.expr.datatypes as dt

from egregora.database.utils import quote_identifier

logger = logging.getLogger(__name__)

# ============================================================================
# Helper Functions
# ============================================================================


def create_table_if_not_exists(
    conn: Any,
    table_name: str,
    schema: ibis.Schema,
    *,
    overwrite: bool = False,
    check_constraints: dict[str, str] | None = None,
) -> None:
    """Create a table using Ibis if it doesn't already exist.

    Args:
        conn: Database connection (Ibis or raw DuckDB)
        table_name: Name of the table to create
        schema: Ibis schema definition
        overwrite: If True, drop existing table first
        check_constraints: Optional dict of constraint_name -> check_expression
                          Example: {"chk_status": "status IN ('draft', 'published')"}

    """
    # Explicitly check if the connection is a raw DuckDB connection.
    # This is more reliable than duck-typing with hasattr.
    is_raw_duckdb_connection = isinstance(conn, duckdb.DuckDBPyConnection)

    if is_raw_duckdb_connection:
        # Raw duckdb connection - build the CREATE TABLE statement with constraints.
        if overwrite:
            conn.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")

        columns_sql = ", ".join(
            f"{quote_identifier(name)} {ibis_to_duckdb_type(dtype)}" for name, dtype in schema.items()
        )

        # Add CHECK constraints to CREATE TABLE statement
        constraint_clauses = []
        if check_constraints:
            for constraint_name, check_expr in check_constraints.items():
                constraint_clauses.append(
                    f"CONSTRAINT {quote_identifier(constraint_name)} CHECK ({check_expr})"
                )

        all_clauses = [columns_sql]
        if constraint_clauses:
            all_clauses.extend(constraint_clauses)

        create_verb = "CREATE TABLE" if overwrite else "CREATE TABLE IF NOT EXISTS"
        create_sql = f"{create_verb} {quote_identifier(table_name)} ({', '.join(all_clauses)})"
        conn.execute(create_sql)
    # Assume Ibis connection for all other cases.
    elif table_name not in conn.list_tables() or overwrite:
        conn.create_table(table_name, schema=schema, overwrite=overwrite)
        # This path is problematic for DuckDB which doesn't support ALTER TABLE ADD CONSTRAINT.
        if check_constraints:
            for constraint_name, check_expr in check_constraints.items():
                add_check_constraint(conn.raw_sql, table_name, constraint_name, check_expr)


def ibis_to_duckdb_type(ibis_type: ibis.expr.datatypes.DataType) -> str:
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
        value_type = ibis_to_duckdb_type(ibis_type.value_type)
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
        quoted_table = quote_identifier(table_name)
        quoted_constraint = quote_identifier(f"pk_{table_name}")
        quoted_col = quote_identifier(column_name)
        sql = f"ALTER TABLE {quoted_table} ADD CONSTRAINT {quoted_constraint} PRIMARY KEY ({quoted_col})"
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
    q_index = quote_identifier(index_name)
    q_table = quote_identifier(table_name)
    q_col = quote_identifier(column_name)

    if index_type == "HNSW":
        sql = (
            f"CREATE INDEX IF NOT EXISTS {q_index} ON {q_table} USING HNSW ({q_col}) WITH (metric = 'cosine')"
        )
    else:
        sql = f"CREATE INDEX IF NOT EXISTS {q_index} ON {q_table} ({q_col})"

    conn.execute(sql)


def add_check_constraint(conn: Any, table_name: str, constraint_name: str, check_expression: str) -> None:
    """Add a CHECK constraint to an existing table.

    Args:
        conn: DuckDB connection (raw, not Ibis)
        table_name: Name of the table
        constraint_name: Name for the constraint
        check_expression: SQL expression for the constraint (e.g., "status IN ('draft', 'published')")

    Note:
        This must be called on raw DuckDB connection, not Ibis connection.
        DuckDB requires ALTER TABLE for check constraints.
        Idempotent: silently succeeds if constraint already exists.

    """
    try:
        quoted_table = quote_identifier(table_name)
        quoted_constraint = quote_identifier(constraint_name)
        sql = f"ALTER TABLE {quoted_table} ADD CONSTRAINT {quoted_constraint} CHECK ({check_expression})"
        conn.execute(sql)
    except duckdb.Error as e:
        # Constraint may already exist - log and continue
        logger.debug("Could not add CHECK constraint to %s: %s", table_name, e)


def get_table_check_constraints(table_name: str) -> dict[str, str]:
    """Get CHECK constraints for a table based on business logic.

    Args:
        table_name: Name of the table

    Returns:
        Dictionary mapping constraint names to CHECK expressions

    Note:
        This function defines business rules at the database level by specifying
        CHECK constraints for enum-like fields. Currently supports:
        - posts.status: Must be one of VALID_POST_STATUSES
        - tasks.status: Must be one of VALID_TASK_STATUSES

    """
    if table_name == "posts":
        valid_values = ", ".join(f"'{status}'" for status in VALID_POST_STATUSES)
        return {"chk_posts_status": f"status IN ({valid_values})"}
    if table_name == "tasks":
        constraints = {}
        valid_statuses = ", ".join(f"'{status}'" for status in VALID_TASK_STATUSES)
        constraints["chk_tasks_status"] = f"status IN ({valid_statuses})"
        valid_task_types = ", ".join(f"'{task_type}'" for task_type in VALID_TASK_TYPES)
        constraints["chk_tasks_task_type"] = f"task_type IN ({valid_task_types})"
        return constraints
    if table_name == "media":
        valid_values = ", ".join(f"'{media_type}'" for media_type in VALID_MEDIA_TYPES)
        return {"chk_media_media_type": f"media_type IN ({valid_values})"}
    if table_name == "annotations":
        valid_values = ", ".join(f"'{parent_type}'" for parent_type in VALID_ANNOTATION_PARENT_TYPES)
        return {"chk_annotations_parent_type": f"parent_type IN ({valid_values})"}

    if table_name == "documents":
        valid_post_statuses = ", ".join(f"'{status}'" for status in VALID_POST_STATUSES)
        return {
            "chk_doc_post_req": "(doc_type != 'post') OR (title IS NOT NULL AND slug IS NOT NULL AND status IS NOT NULL)",
            "chk_doc_post_status": f"(doc_type != 'post') OR (status IN ({valid_post_statuses}))",
            "chk_doc_profile_req": "(doc_type != 'profile') OR (title IS NOT NULL AND subject_uuid IS NOT NULL)",
            "chk_doc_journal_req": "(doc_type != 'journal') OR (title IS NOT NULL AND window_start IS NOT NULL AND window_end IS NOT NULL)",
            "chk_doc_media_req": "(doc_type != 'media') OR (filename IS NOT NULL)",
        }

    return {}


# ============================================================================
# Core Tables (Append-Only)
# ============================================================================

# Valid status values for business logic enforcement
VALID_POST_STATUSES = ("draft", "published", "archived")
VALID_TASK_STATUSES = ("pending", "processing", "completed", "failed", "superseded")
VALID_MEDIA_TYPES = ("image", "video", "audio")
VALID_TASK_TYPES = ("generate_banner", "update_profile", "enrich_media", "enrich_url")
VALID_ANNOTATION_PARENT_TYPES = ("message", "post", "annotation")

# Common columns for all types
BASE_COLUMNS = {
    "id": dt.string,  # Deterministic UUID/Slug
    "content": dt.string,  # Markdown/Text content
    "created_at": dt.timestamp,  # Insertion time
    "source_checksum": dt.string,  # Hash for deduplication/change detection
}

# 1. POSTS TABLE
POSTS_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "title": dt.string,
        "slug": dt.string,
        "date": dt.date,
        "summary": dt.string,
        "authors": dt.Array(dt.string),  # List of Author UUIDs
        "tags": dt.Array(dt.string),
        "status": dt.string,  # 'published', 'draft'
    }
)

# 2. PROFILES TABLE
PROFILES_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "subject_uuid": dt.string,
        "title": dt.string,  # Was 'name'
        "alias": dt.string,
        "summary": dt.string,  # Was 'bio'
        "avatar_url": dt.string,
        "interests": dt.Array(dt.string),
    }
)

# 3. MEDIA TABLE (Metadata only, content is binary/external)
MEDIA_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "filename": dt.string,
        "mime_type": dt.string,
        "media_type": dt.string,  # 'image', 'video', 'audio'
        "phash": dt.string,  # Perceptual hash for dedup
    }
)

# 4. JOURNALS TABLE
JOURNALS_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "title": dt.string,  # Was 'window_label'
        "window_start": dt.timestamp,
        "window_end": dt.timestamp,
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
        # run_id is no longer part of the schema in V2, but was in V1.
        # Removing run_id dependency for clean break.
    }
)

# ============================================================================
# Unified Schema
# ============================================================================

UNIFIED_SCHEMA = ibis.schema(
    {
        **dict(POSTS_SCHEMA.items()),
        **dict(PROFILES_SCHEMA.items()),
        **dict(MEDIA_SCHEMA.items()),
        **dict(JOURNALS_SCHEMA.items()),
        "doc_type": dt.String(nullable=False),
        "status": dt.String(nullable=False),
        "extensions": dt.json,
    }
)

# ============================================================================
# Views
# ============================================================================

DOCUMENTS_VIEW_SQL = """
CREATE OR REPLACE VIEW documents_view AS
    SELECT id, 'post' as type, content, created_at, title, slug, NULL as subject_uuid FROM posts
    UNION ALL
    SELECT id, 'profile' as type, content, created_at, title, NULL as slug, subject_uuid FROM profiles
    UNION ALL
    SELECT id, 'journal' as type, content, created_at, title, NULL as slug, NULL as subject_uuid FROM journals
    UNION ALL
    SELECT id, 'media' as type, content, created_at, NULL as title, NULL as slug, NULL as subject_uuid FROM media
    UNION ALL
    SELECT id, 'annotation' as type, content, created_at, NULL as title, NULL as slug, NULL as subject_uuid FROM annotations
"""

# ============================================================================
# Ingestion Schemas
# ============================================================================

# ----------------------------------------------------------------------------
# Ingestion Staging Schema (Was Ingestion Message Schema)
# ----------------------------------------------------------------------------

STAGING_MESSAGES_SCHEMA = ibis.schema(
    {
        # Identity
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
# Annotations Schema
# ----------------------------------------------------------------------------

ANNOTATIONS_SCHEMA = ibis.schema(
    {
        **BASE_COLUMNS,
        "parent_id": dt.string,  # Reference to what is being annotated
        "parent_type": dt.string,  # 'message', 'post', 'annotation'
        "author_id": dt.string,  # Author of the annotation
        # "commentary" is mapped to "content" in BASE_COLUMNS
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
