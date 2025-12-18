"""Database migration utilities.

This module provides logic to migrate existing database tables to the latest schema versions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from egregora.database.ir_schema import quote_identifier

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager

logger = logging.getLogger(__name__)


def migrate_database(storage: DuckDBStorageManager) -> None:
    """Migrate the database to the latest schema.

    Currently handles:
    1. Migration of the 'documents' table to UNIFIED_SCHEMA:
       - Adds 'doc_type' column (default: 'post')
       - Adds 'extensions' column (default: '{}')

    Args:
        storage: The storage manager instance.

    """
    logger.info("Starting database migration...")

    _migrate_documents_table(storage)

    logger.info("Database migration completed.")


def _migrate_documents_table(storage: DuckDBStorageManager) -> None:
    """Migrate the 'documents' table to match UNIFIED_SCHEMA."""
    table_name = "documents"

    if not storage.table_exists(table_name):
        logger.info("Table '%s' does not exist. Skipping migration.", table_name)
        return

    # Get existing columns
    existing_columns = storage.get_table_columns(table_name, refresh=True)

    # We want to check for missing columns that are in UNIFIED_SCHEMA
    # For now, we specifically target 'doc_type' and 'extensions' as per requirements
    quoted_table = quote_identifier(table_name)

    # 1. doc_type
    if "doc_type" not in existing_columns:
        logger.info("Migrating '%s': Adding column 'doc_type'", table_name)
        # We use raw SQL for ALTER TABLE
        # UNIFIED_SCHEMA defines it as dt.String (nullable=False)
        # We default to 'post' as a safe fallback for existing content
        storage.execute_sql(f"ALTER TABLE {quoted_table} ADD COLUMN doc_type VARCHAR DEFAULT 'post'")

    # 2. extensions
    if "extensions" not in existing_columns:
        logger.info("Migrating '%s': Adding column 'extensions'", table_name)
        # UNIFIED_SCHEMA defines it as dt.JSON (nullable=False)
        # We default to empty JSON object '{}'
        storage.execute_sql(f"ALTER TABLE {quoted_table} ADD COLUMN extensions JSON DEFAULT '{{}}'")
