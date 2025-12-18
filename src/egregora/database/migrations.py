"""Database migration utilities for Egregora V3."""

from __future__ import annotations

import logging
from typing import Any

import ibis

from egregora.database.ir_schema import UNIFIED_SCHEMA, create_table_if_not_exists, quote_identifier

logger = logging.getLogger(__name__)


def migrate_documents_table(conn: Any) -> None:
    """Ensure the documents table matches the V3 UNIFIED_SCHEMA.

    This function performs the following actions:
    1. Creates the table if it does not exist.
    2. Checks for missing columns in the existing table.
    3. Adds missing columns with appropriate defaults.

    Args:
        conn: DuckDB connection (raw or Ibis backend, though raw is preferred for DDL)

    """
    # 1. Ensure table exists (idempotent)
    # Check if table exists first to decide if we need to create it completely
    table_exists = False
    if hasattr(conn, "list_tables"):
        if "documents" in conn.list_tables():
            table_exists = True
    else:
        # Raw connection
        res = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'documents'"
        ).fetchone()
        if res and res[0] > 0:
            table_exists = True

    if not table_exists:
        logger.info("Creating 'documents' table from scratch using UNIFIED_SCHEMA.")
        create_table_if_not_exists(conn, "documents", UNIFIED_SCHEMA)
        return

    # 2. Check for missing columns
    # Get existing columns
    # Normalize connection access for introspection
    # We prefer using raw SQL DESCRIBE for ground truth
    try:
        if hasattr(conn, "execute"):
            columns_info = conn.execute("DESCRIBE documents").fetchall()
        elif hasattr(conn, "raw_sql"):
            columns_info = conn.raw_sql("DESCRIBE documents").fetchall()
        else:
            raise ValueError("Unknown connection type")

        existing_columns = {row[0] for row in columns_info}
    except Exception:
        logger.exception("Failed to describe documents table")
        raise

    # 3. Add missing columns
    required_columns = UNIFIED_SCHEMA.names

    # Defaults for new columns
    defaults = {
        "doc_type": "'post'",  # Default to 'post' for existing generic items
        "status": "'published'",  # Assume existing items are published
        "extensions": "'{}'",
        "internal_metadata": "'{}'",
        "content_type": "'text/plain'",  # Fallback
    }

    for col_name in required_columns:
        if col_name not in existing_columns:
            logger.info(f"Migrating 'documents' table: Adding column '{col_name}'")

            # Determine type from schema
            ibis_type = UNIFIED_SCHEMA[col_name]
            sql_type = _ibis_type_to_sql(ibis_type)

            # Get default value if available
            default_val = defaults.get(col_name, "NULL")

            alter_sql = f"ALTER TABLE documents ADD COLUMN {quote_identifier(col_name)} {sql_type} DEFAULT {default_val}"

            if hasattr(conn, "raw_sql"):
                conn.raw_sql(alter_sql)
            else:
                conn.execute(alter_sql)


def _ibis_type_to_sql(ibis_type: ibis.expr.datatypes.DataType) -> str:
    """Helper to convert Ibis type to SQL type string for ALTER TABLE."""
    # This duplicates logic from ir_schema._ibis_to_duckdb_type but that one is private.
    # We should ideally expose it or duplicate it safely.
    # For now, implementing a simplified version sufficient for the new columns.

    if ibis_type.is_string():
        return "VARCHAR"
    if ibis_type.is_json():
        return "JSON"
    if ibis_type.is_timestamp():
        return "TIMESTAMP WITH TIME ZONE"
    if ibis_type.is_boolean():
        return "BOOLEAN"
    if ibis_type.is_integer():
        return "BIGINT"

    # Fallback
    return str(ibis_type).upper()
