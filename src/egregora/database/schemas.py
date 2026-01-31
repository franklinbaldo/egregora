"""Database schema definitions for Egregora V2 (Clean Break).

This module defines the strictly typed, append-only tables for the new architecture.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import duckdb
import ibis
import ibis.expr.datatypes as dt

from egregora.database.utils import quote_identifier

if TYPE_CHECKING:
    from ibis.backends import BaseBackend

logger = logging.getLogger(__name__)

__all__ = [
    "ANNOTATIONS_SCHEMA",
    "ASSET_CACHE_SCHEMA",
    "ELO_HISTORY_SCHEMA",
    "ELO_RATINGS_SCHEMA",
    "GIT_COMMITS_SCHEMA",
    "GIT_REFS_SCHEMA",
    "STAGING_MESSAGES_SCHEMA",
    "TASKS_SCHEMA",
    "UNIFIED_SCHEMA",
    "add_check_constraint",
    "create_index",
    "create_table_if_not_exists",
    "get_table_check_constraints",
    "get_table_foreign_keys",
    "ibis_to_duckdb_type",
]

# Connection TypeAlias for better readability
# Supports both DuckDB raw connection and Ibis backends
type DatabaseConnection = duckdb.DuckDBPyConnection | "BaseBackend"

# ============================================================================
# Helper Functions
# ============================================================================


def create_table_if_not_exists(
    conn: DatabaseConnection,
    table_name: str,
    schema: ibis.Schema,
    *,
    overwrite: bool = False,
    check_constraints: dict[str, str] | None = None,
    primary_key: str | list[str] | None = None,
    foreign_keys: list[str] | None = None,
) -> None:
    """Create a table using Ibis if it doesn't already exist.

    Args:
        conn: Database connection (Ibis or raw DuckDB)
        table_name: Name of the table to create
        schema: Ibis schema definition
        overwrite: If True, drop existing table first
        check_constraints: Optional dict of constraint_name -> check_expression
                          Example: {"chk_status": "status IN ('draft', 'published')"}
        primary_key: Optional column name (or list of names) to set as PRIMARY KEY
        foreign_keys: Optional list of foreign key constraint strings
                      Example: ["FOREIGN KEY (parent_id) REFERENCES documents(id)"]

    """
    # Explicitly check if the connection is a raw DuckDB connection.
    # This is more reliable than duck-typing with hasattr.
    if isinstance(conn, duckdb.DuckDBPyConnection):
        # Raw duckdb connection - build the CREATE TABLE statement with constraints.
        if overwrite:
            conn.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")

        columns_sql = ", ".join(
            f"{quote_identifier(name)} {ibis_to_duckdb_type(dtype)}" for name, dtype in schema.items()
        )

        all_clauses = [columns_sql]

        # Add PRIMARY KEY
        if primary_key:
            if isinstance(primary_key, list):
                pk_cols = ", ".join(quote_identifier(c) for c in primary_key)
            else:
                pk_cols = quote_identifier(primary_key)
            all_clauses.append(f"PRIMARY KEY ({pk_cols})")

        # Add FOREIGN KEYs
        if foreign_keys:
            all_clauses.extend(foreign_keys)

        # Add CHECK constraints to CREATE TABLE statement
        if check_constraints:
            for constraint_name, check_expr in check_constraints.items():
                all_clauses.append(f"CONSTRAINT {quote_identifier(constraint_name)} CHECK ({check_expr})")

        create_verb = "CREATE TABLE" if overwrite else "CREATE TABLE IF NOT EXISTS"
        create_sql = f"{create_verb} {quote_identifier(table_name)} ({', '.join(all_clauses)})"
        conn.execute(create_sql)
    else:
        # Assume Ibis connection for all other cases.
        # We need to cast because mypy doesn't fully narrow the negative case of isinstance
        # when the other type is behind a TYPE_CHECKING guard or Any-like.
        ibis_conn = cast("BaseBackend", conn)

        if table_name not in ibis_conn.list_tables() or overwrite:
            ibis_conn.create_table(table_name, schema=schema, overwrite=overwrite)
            # This path is problematic for DuckDB which doesn't support ALTER TABLE ADD CONSTRAINT.
            # But we try to apply what we can via helpers.
            if primary_key:
                add_primary_key(conn, table_name, primary_key)
            if check_constraints:
                for constraint_name, check_expr in check_constraints.items():
                    add_check_constraint(conn, table_name, constraint_name, check_expr)
            # Note: Foreign keys via ALTER TABLE are tricky/limited in some backends or contexts,
            # so they are best handled in the raw_duckdb path or via migration.


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


def _execute_on_connection(conn: DatabaseConnection, sql: str) -> None:
    """Execute raw SQL on either an Ibis backend or a DuckDB connection."""
    if isinstance(conn, duckdb.DuckDBPyConnection):
        conn.execute(sql)
    elif hasattr(conn, "raw_sql"):
        # Ibis backends typically have raw_sql
        conn.raw_sql(sql)
    elif hasattr(conn, "execute"):
        # Some Ibis backends or custom connections might expose execute
        conn.execute(sql)
    else:
        logger.warning("Could not execute SQL on connection: %s", conn)


def add_primary_key(conn: DatabaseConnection, table_name: str, column_name: str | list[str]) -> None:
    """Add a primary key constraint to an existing table.

    Args:
        conn: Database connection (Ibis or raw DuckDB)
        table_name: Name of the table
        column_name: Column(s) to use as primary key

    Note:
        DuckDB requires ALTER TABLE for primary key constraints.

    """
    try:
        quoted_table = quote_identifier(table_name)
        quoted_constraint = quote_identifier(f"pk_{table_name}")

        if isinstance(column_name, list):
            quoted_cols = ", ".join(quote_identifier(c) for c in column_name)
        else:
            quoted_cols = quote_identifier(column_name)

        sql = f"ALTER TABLE {quoted_table} ADD CONSTRAINT {quoted_constraint} PRIMARY KEY ({quoted_cols})"
        _execute_on_connection(conn, sql)
    except (duckdb.Error, RuntimeError) as e:
        # Constraint may already exist - log and continue
        # RuntimeError can happen from Ibis backends on SQL error
        logger.debug("Could not add primary key to %s.%s: %s", table_name, column_name, e)


def ensure_identity_column(
    conn: DatabaseConnection, table_name: str, column_name: str, *, generated: str = "ALWAYS"
) -> None:
    """Ensure a column is configured as an identity column in DuckDB."""
    if generated not in ("ALWAYS", "BY DEFAULT"):
        msg = f"Invalid identity generation mode: {generated!r}"
        raise ValueError(msg)

    try:
        quoted_table = quote_identifier(table_name)
        quoted_column = quote_identifier(column_name)
        sql = f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_column} SET GENERATED {generated} AS IDENTITY"
        _execute_on_connection(conn, sql)
    except (duckdb.Error, RuntimeError) as e:
        # Identity column setup failure is non-fatal (might already exist or not supported by backend)
        # duckdb.Error is likely, but catching RuntimeError to be safe against different backends
        logger.debug(
            "Could not set identity on %s.%s (generated=%s): %s", table_name, column_name, generated, e
        )


def create_index(
    conn: DatabaseConnection, table_name: str, index_name: str, column_name: str, index_type: str = "HNSW"
) -> None:
    """Create an index on a table.

    Args:
        conn: Database connection (Ibis or raw DuckDB)
        table_name: Name of the table
        index_name: Name for the index
        column_name: Column to index
        index_type: Type of index (HNSW for vector search, standard otherwise)

    Note:
        For vector columns, use index_type='HNSW' with cosine metric (optimized for 768-dim embeddings).
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

    _execute_on_connection(conn, sql)


def add_check_constraint(
    conn: DatabaseConnection, table_name: str, constraint_name: str, check_expression: str
) -> None:
    """Add a CHECK constraint to an existing table.

    Args:
        conn: Database connection (Ibis or raw DuckDB)
        table_name: Name of the table
        constraint_name: Name for the constraint
        check_expression: SQL expression for the constraint (e.g., "status IN ('draft', 'published')")

    Note:
        DuckDB requires ALTER TABLE for check constraints.
        Idempotent: silently succeeds if constraint already exists.

    """
    try:
        quoted_table = quote_identifier(table_name)
        quoted_constraint = quote_identifier(constraint_name)
        sql = f"ALTER TABLE {quoted_table} ADD CONSTRAINT {quoted_constraint} CHECK ({check_expression})"
        _execute_on_connection(conn, sql)
    except (duckdb.Error, RuntimeError) as e:
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
    if table_name == "annotations":
        valid_values = ", ".join(f"'{parent_type}'" for parent_type in VALID_ANNOTATION_PARENT_TYPES)
        return {"chk_annotations_parent_type": f"parent_type IN ({valid_values})"}

    if table_name == "documents":
        valid_post_statuses = ", ".join(f"'{status}'" for status in VALID_POST_STATUSES)
        valid_media_types = ", ".join(f"'{media_type}'" for media_type in VALID_MEDIA_TYPES)
        return {
            "chk_doc_post_req": "(doc_type != 'post') OR (title IS NOT NULL AND slug IS NOT NULL AND status IS NOT NULL)",
            "chk_doc_post_status": f"(doc_type != 'post') OR (status IN ({valid_post_statuses}))",
            "chk_doc_profile_req": "(doc_type != 'profile') OR (title IS NOT NULL AND subject_uuid IS NOT NULL)",
            "chk_doc_journal_req": "(doc_type != 'journal') OR (title IS NOT NULL AND window_start IS NOT NULL AND window_end IS NOT NULL)",
            "chk_doc_media_req": "(doc_type != 'media') OR (filename IS NOT NULL)",
            "chk_doc_media_type": f"(doc_type != 'media') OR (media_type IN ({valid_media_types}))",
        }

    return {}


def get_table_foreign_keys(table_name: str) -> list[str]:
    """Get Foreign Key constraints for a table.

    Args:
        table_name: Name of the table

    Returns:
        List of FOREIGN KEY clause strings.
        Example: ["FOREIGN KEY (parent_id) REFERENCES documents(id)"]

    """
    if table_name == "annotations":
        return ["FOREIGN KEY (parent_id) REFERENCES documents(id)"]
    return []


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

# 1. POSTS TABLE (Deprecated: Merged into documents)
# Keeping structure here to compose UNIFIED_SCHEMA until Ibis supports cleaner union
_POSTS_COLUMNS = {
    **BASE_COLUMNS,
    "title": dt.string,
    "slug": dt.string,
    "date": dt.date,
    "summary": dt.string,
    "authors": dt.Array(dt.string),  # List of Author UUIDs
    "tags": dt.Array(dt.string),
    "status": dt.string,  # 'published', 'draft'
}

# 2. PROFILES TABLE (Deprecated: Merged into documents)
_PROFILES_COLUMNS = {
    **BASE_COLUMNS,
    "subject_uuid": dt.string,
    "title": dt.string,  # Was 'name'
    "alias": dt.string,
    "summary": dt.string,  # Was 'bio'
    "avatar_url": dt.string,
    "interests": dt.Array(dt.string),
}

# 3. MEDIA TABLE (Metadata only, content is binary/external)
# Also used for standalone MEDIA table if needed, but primarily for Unified
_MEDIA_COLUMNS = {
    "filename": dt.string,
    "mime_type": dt.string,
    "media_type": dt.string,  # 'image', 'video', 'audio'
    "phash": dt.string,  # Perceptual hash for dedup
}

# 4. JOURNALS TABLE (Deprecated: Merged into documents)
_JOURNALS_COLUMNS = {
    **BASE_COLUMNS,
    "title": dt.string,  # Was 'window_label'
    "window_start": dt.timestamp,
    "window_end": dt.timestamp,
}

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
        **_POSTS_COLUMNS,
        **_PROFILES_COLUMNS,
        **_MEDIA_COLUMNS,
        **_JOURNALS_COLUMNS,
        "doc_type": dt.String(nullable=False),
        "status": dt.String(nullable=False),
        "extensions": dt.json,
    }
)

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
        "post_slug": dt.string,
        "rating": dt.float64,
        "comparisons": dt.int64,
        "wins": dt.int64,
        "losses": dt.int64,
        "ties": dt.int64,
        "last_updated": dt.Timestamp(timezone="UTC"),
        "created_at": dt.Timestamp(timezone="UTC"),
    }
)

ELO_HISTORY_SCHEMA = ibis.schema(
    {
        "comparison_id": dt.string,
        "post_a_slug": dt.string,
        "post_b_slug": dt.string,
        "winner": dt.string,  # "a", "b", or "tie"
        "rating_a_before": dt.float64,
        "rating_b_before": dt.float64,
        "rating_a_after": dt.float64,
        "rating_b_after": dt.float64,
        "timestamp": dt.Timestamp(timezone="UTC"),
        "reader_feedback": dt.string,  # JSON string with comments/ratings
    }
)

# ----------------------------------------------------------------------------
# Git History Cache Schema (Context Layer)
# ----------------------------------------------------------------------------

GIT_COMMITS_SCHEMA = ibis.schema(
    {
        "repo_path": dt.string,  # Logical path in repo (e.g., 'src/main.py')
        "commit_sha": dt.string,  # SHA-1
        "commit_timestamp": dt.Timestamp(timezone="UTC"),
        "author": dt.string(nullable=True),
        "message": dt.string(nullable=True),
        "change_type": dt.string,  # 'A', 'M', 'D', 'R'
        "stats": dt.JSON(nullable=True),  # e.g. {"insertions": 10, "deletions": 5}
    }
)

ASSET_CACHE_SCHEMA = ibis.schema(
    {
        "url": dt.string,
        "content_hash": dt.string,
        "content_type": dt.string,
        "content": dt.binary,
        "etag": dt.string(nullable=True),
        "last_modified": dt.string(nullable=True),
        "fetched_at": dt.Timestamp(timezone="UTC"),
        "expires_at": dt.Timestamp(timezone="UTC", nullable=True),
        "metadata": dt.JSON(nullable=True),
    }
)

GIT_REFS_SCHEMA = ibis.schema(
    {
        "ref_name": dt.string,  # e.g., 'refs/heads/main', 'refs/tags/v1.0'
        "commit_sha": dt.string,  # SHA-1
        "is_tag": dt.boolean,
        "is_remote": dt.boolean,
    }
)
