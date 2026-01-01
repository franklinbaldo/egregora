
"""V3 Schema Migration Script."""
import logging
import duckdb
import json
from datetime import date, datetime, UTC

from egregora.database.schemas import V3_DOCUMENTS_SCHEMA, ibis_to_duckdb_type

logger = logging.getLogger(__name__)


def migrate_to_v3_documents_table(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Applies the V3_DOCUMENTS_SCHEMA to a legacy 'documents' table.

    This migration is idempotent. It uses a safe "create-copy-swap" pattern
    to handle schema changes, including adding NOT NULL constraints and
    transforming data from old columns into new JSON structures.
    """
    try:
        result = conn.execute("PRAGMA table_info('documents')").fetchall()
        existing_columns = {row[1] for row in result}
    except duckdb.CatalogException:
        # If the table doesn't exist at all, there's nothing to migrate.
        logger.info("Table 'documents' does not exist. No migration needed.")
        return

    # Idempotency check: If a key V3 column already exists, assume migration is done.
    if "internal_metadata" in existing_columns:
        logger.info("V3 schema already applied. No migration needed.")
        return

    logger.info("Legacy schema detected. Starting migration to V3 'documents' table.")

    temp_table_name = "documents_v3_temp"
    conn.execute(f"DROP TABLE IF EXISTS {temp_table_name}")

    # 1. Create the new table with the correct V3 schema
    columns_sql = ", ".join(
        f'"{name}" {ibis_to_duckdb_type(dtype)}{"" if dtype.nullable else " NOT NULL"}'
        for name, dtype in V3_DOCUMENTS_SCHEMA.items()
    )
    create_temp_table_sql = f"CREATE TABLE {temp_table_name} ({columns_sql});"
    conn.execute(create_temp_table_sql)

    # 2. Prepare SELECT expressions to copy and transform data
    select_expressions = []
    for name, dtype in V3_DOCUMENTS_SCHEMA.items():
        if name in existing_columns:
            # Direct copy for existing columns
            select_expressions.append(f'"{name}"')
        else:
            # Handle new or transformed columns with defaults
            default = "NULL"
            if not dtype.nullable:
                if dtype.is_json():
                    default = "'[]'"  # Default for authors, links, etc.
                elif dtype.is_string():
                    default = "''"
                elif dtype.is_timestamp():
                    default = f"'{datetime.now(UTC).isoformat()}'"
            select_expressions.append(f'{default} AS "{name}"')

    # Custom transformation for internal_metadata
    # We build a JSON object from legacy columns
    meta_expression = """
    json_object(
        'legacy_slug', slug,
        'legacy_date', date::VARCHAR
    ) AS internal_metadata
    """
    # Replace the placeholder 'NULL AS "internal_metadata"'
    select_expressions = [
        meta_expression if 'AS "internal_metadata"' in col else col for col in select_expressions
    ]
    # Set doc_type default
    select_expressions = [
        "'post' AS doc_type" if 'AS "doc_type"' in col else col for col in select_expressions
    ]


    # 3. Copy data from old table to new table
    insert_sql = f"""
    INSERT INTO {temp_table_name}
    SELECT {', '.join(select_expressions)}
    FROM documents;
    """
    conn.execute(insert_sql)

    # 4. Atomically replace the old table with the new one
    conn.execute("DROP TABLE documents;")
    conn.execute(f"ALTER TABLE {temp_table_name} RENAME TO documents;")

    logger.info("Successfully migrated 'documents' table to V3 schema.")
