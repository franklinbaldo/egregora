"""Schema Migration Script."""

import logging

import duckdb

# Import the target schema and the type conversion utility
from egregora.database.schemas import UNIFIED_SCHEMA, ibis_to_duckdb_type, quote_identifier

logger = logging.getLogger(__name__)


def _get_existing_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    """Get the existing columns from a table."""
    quoted_name = quote_identifier(table_name)
    result = conn.execute(f"PRAGMA table_info({quoted_name})").fetchall()
    return {row[1] for row in result}


def _build_create_table_sql(table_name: str) -> str:
    """Define the new schema with NOT NULL constraints."""
    columns_sql = ", ".join(
        f'{quote_identifier(name)} {ibis_to_duckdb_type(dtype)}{" NOT NULL" if not dtype.nullable else ""}'
        for name, dtype in UNIFIED_SCHEMA.items()
    )
    quoted_table = quote_identifier(table_name)
    return f"CREATE TABLE {quoted_table} ({columns_sql});"


def _build_insert_select_sql(temp_table: str, existing_columns: set[str]) -> str:
    """Prepare the SELECT statement to copy and transform data."""
    column_names = [quote_identifier(name) for name in UNIFIED_SCHEMA]
    select_expressions = []
    for name in UNIFIED_SCHEMA:
        quoted_name = quote_identifier(name)
        if name in existing_columns:
            select_expressions.append(quoted_name)
        elif name == "doc_type":
            select_expressions.append("'note' AS doc_type")
        elif name == "status":
            select_expressions.append("'draft' AS status")
        else:
            select_expressions.append(f"NULL AS {quoted_name}")

    # Note: 'documents' is the source table, hardcoded here as per migration logic
    select_sql = f"SELECT {', '.join(select_expressions)} FROM documents"  # nosec B608
    quoted_temp = quote_identifier(temp_table)
    return f"INSERT INTO {quoted_temp} ({', '.join(column_names)}) {select_sql};"


def migrate_documents_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Applies the Pure UNIFIED_SCHEMA to an existing 'documents' table.

    This migration is idempotent and robustly handles NOT NULL constraints
    by creating a new table, copying data, and replacing the old table.
    """
    existing_columns = _get_existing_columns(conn, "documents")

    # Check if migration is needed
    if "doc_type" in existing_columns and "status" in existing_columns:
        logger.info("Schema is already up to date. No migration needed.")
        return

    temp_table_name = "documents_temp"

    create_sql = _build_create_table_sql(temp_table_name)
    logger.info(f"Creating temporary table: {temp_table_name}")
    conn.execute(create_sql)

    insert_sql = _build_insert_select_sql(temp_table_name, existing_columns)
    logger.info(f"Copying data to temporary table: {temp_table_name}")
    conn.execute(insert_sql)

    # Replace the old table
    logger.info("Replacing old table with new one.")
    conn.execute("DROP TABLE documents;")
    quoted_temp = quote_identifier(temp_table_name)
    conn.execute(f"ALTER TABLE {quoted_temp} RENAME TO documents;")
