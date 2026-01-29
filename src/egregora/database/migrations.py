"""Schema Migration Script."""

import logging

import duckdb

# Import the target schema and the type conversion utility
from egregora.database.schemas import UNIFIED_SCHEMA, get_table_check_constraints, ibis_to_duckdb_type
from egregora.database.utils import quote_identifier

logger = logging.getLogger(__name__)


def _get_existing_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    """Get the existing columns from a table."""
    result = conn.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
    return {row[1] for row in result}


def _verify_all_constraints_present(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    """Verify that all expected constraints are present in the table."""
    try:
        # Get existing constraints
        result = conn.execute(
            "SELECT constraint_name FROM duckdb_constraints() WHERE table_name=? AND constraint_type='CHECK'",
            [table_name],
        ).fetchall()
        existing_constraints = {row[0] for row in result}

        # Get expected constraints
        expected_constraints = get_table_check_constraints(table_name)

        # Check if all expected constraints are in existing constraints
        return all(name in existing_constraints for name in expected_constraints)

    except duckdb.Error:
        # Fallback if system table is unavailable or changed
        return False


def _build_documents_create_table_sql(table_name: str) -> str:
    """Define the new schema with NOT NULL constraints and CHECK constraints."""
    columns_sql = ", ".join(
        f"{quote_identifier(name)} {ibis_to_duckdb_type(dtype)}{' NOT NULL' if not dtype.nullable else ''}"
        for name, dtype in UNIFIED_SCHEMA.items()
    )

    check_constraints = get_table_check_constraints("documents")
    constraint_clauses = []
    for constraint_name, check_expr in check_constraints.items():
        constraint_clauses.append(f"CONSTRAINT {quote_identifier(constraint_name)} CHECK ({check_expr})")

    all_clauses = [columns_sql]
    if constraint_clauses:
        all_clauses.extend(constraint_clauses)

    return f"CREATE TABLE {quote_identifier(table_name)} ({', '.join(all_clauses)});"


def _build_documents_insert_select_sql(temp_table: str, existing_columns: set[str]) -> str:
    """Prepare the SELECT statement to copy and transform data."""
    column_names = [f"{quote_identifier(name)}" for name in UNIFIED_SCHEMA]
    select_expressions = []
    for name in UNIFIED_SCHEMA:
        if name in existing_columns:
            select_expressions.append(f"{quote_identifier(name)}")
        elif name == "doc_type":
            select_expressions.append("'note' AS doc_type")
        elif name == "status":
            select_expressions.append("'draft' AS status")
        else:
            select_expressions.append(f"NULL AS {quote_identifier(name)}")

    select_sql = f"SELECT {', '.join(select_expressions)} FROM documents"  # nosec B608
    return f"INSERT INTO {quote_identifier(temp_table)} ({', '.join(column_names)}) {select_sql};"  # nosec B608


def migrate_media_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Migrate legacy media table to documents table."""
    # Check if media table exists
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if "media" not in tables:
        return

    logger.info("Migrating legacy media table to documents...")

    # Check if documents table exists (it should, but just in case)
    if "documents" not in tables:
        logger.warning("Documents table missing, skipping media migration.")
        return

    columns_to_copy = [
        "id",
        "content",
        "created_at",
        "source_checksum",
        "filename",
        "mime_type",
        "media_type",
        "phash",
    ]

    target_columns = [*columns_to_copy, "doc_type", "status"]
    select_columns = [*columns_to_copy, "'media'", "'published'"]

    target_cols_str = ", ".join(quote_identifier(c) for c in target_columns)
    select_cols_str = ", ".join(c if c.startswith("'") else quote_identifier(c) for c in select_columns)

    insert_sql = f"INSERT INTO documents ({target_cols_str}) SELECT {select_cols_str} FROM media"

    logger.info(f"Copying media rows: {insert_sql}")
    conn.execute(insert_sql)

    # Drop legacy table
    logger.info("Dropping legacy media table.")
    conn.execute("DROP TABLE media")


def migrate_documents_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Applies the Pure UNIFIED_SCHEMA to an existing 'documents' table.

    This migration is idempotent and robustly handles NOT NULL constraints
    by creating a new table, copying data, and replacing the old table.
    """
    existing_columns = _get_existing_columns(conn, "documents")
    constraints_ok = _verify_all_constraints_present(conn, "documents")

    # Check if migration is needed
    # If we have all columns AND all expected constraints, we skip.
    needs_schema_migration = not (
        "doc_type" in existing_columns and "status" in existing_columns and constraints_ok
    )

    if needs_schema_migration:
        temp_table_name = "documents_temp"

        conn.execute(f"DROP TABLE IF EXISTS {quote_identifier(temp_table_name)}")
        create_sql = _build_documents_create_table_sql(temp_table_name)
        logger.info(f"Creating temporary table: {temp_table_name}")
        conn.execute(create_sql)

        insert_sql = _build_documents_insert_select_sql(temp_table_name, existing_columns)
        logger.info(f"Copying data to temporary table: {temp_table_name}")
        conn.execute(insert_sql)

        # Replace the old table
        logger.info("Replacing old table with new one.")
        conn.execute("DROP TABLE documents;")
        conn.execute(f"ALTER TABLE {temp_table_name} RENAME TO documents;")
    else:
        logger.info("Schema is already up to date. No migration needed.")

    # Consolidate Media (Safe to run now as Schema is guaranteed V3)
    # Media consolidation logic (migrate_media_table) was removed in V3 Pure.
