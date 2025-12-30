"""Database migration scripts for Egregora."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import ibis
import ibis.expr.datatypes as dt

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

from egregora.database.schemas import ibis_to_duckdb_type

logger = logging.getLogger(__name__)

# This is the V3 "unified" schema that the `documents` table should conform to.
# It's derived from `egregora_v3.core.types.Entry` and `Document`.
UNIFIED_SCHEMA = ibis.schema(
    {
        # --- Core Entry Fields ---
        "id": dt.String(nullable=False),
        "title": dt.String(nullable=False),
        "updated": dt.Timestamp(timezone="UTC", nullable=False),
        "published": dt.Timestamp(timezone="UTC"),
        "links": dt.JSON,
        "authors": dt.JSON,
        "categories": dt.JSON,
        "summary": dt.String(),
        "content": dt.String(),
        "content_type": dt.String(),
        "source": dt.JSON,
        "in_reply_to": dt.JSON,
        # --- Public Extensions ---
        "extensions": dt.JSON,
        # --- Internal Metadata ---
        "internal_metadata": dt.JSON,
        # --- Document-specific Fields ---
        "doc_type": dt.String(),
        "status": dt.String(),
        "searchable": dt.Boolean(),
        "url_path": dt.String(),
        # --- Legacy Fields to Preserve ---
        "created_at": dt.Timestamp(timezone="UTC"),
        "source_checksum": dt.String(),
    }
)


def migrate_documents_table(con: BaseBackend) -> None:
    """Ensures the 'documents' table has all columns from the UNIFIED_SCHEMA.

    This function is idempotent and will only add columns that are missing.
    """
    if "documents" not in con.list_tables():
        logger.info("Table 'documents' does not exist. Skipping migration.")
        return

    table = con.table("documents")
    existing_columns = {col.lower() for col in table.columns}

    logger.info(f"Existing columns in 'documents': {sorted(existing_columns)}")

    for col_name, col_type in UNIFIED_SCHEMA.items():
        if col_name.lower() not in existing_columns:
            sql_type = ibis_to_duckdb_type(col_type)
            try:
                # Use raw_sql to execute DDL statements directly
                con.raw_sql(f'ALTER TABLE documents ADD COLUMN "{col_name}" {sql_type}')
                logger.info(f"Added column '{col_name}' to 'documents' table.")
            except Exception as e:
                logger.exception(f"Failed to add column '{col_name}': {e}")
