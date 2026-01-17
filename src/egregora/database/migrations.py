"""Schema Migration Script."""

import logging

import duckdb

# Import the target schema and the type conversion utility
from egregora.database.schemas import UNIFIED_SCHEMA, ibis_to_duckdb_type

logger = logging.getLogger(__name__)


def _get_existing_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    """Get the existing columns from a table."""
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {row[1] for row in result}


def _build_create_table_sql(table_name: str) -> str:
    """Define the new schema with NOT NULL constraints."""
    columns_sql = ", ".join(
        f'"{name}" {ibis_to_duckdb_type(dtype)}{" NOT NULL" if not dtype.nullable else ""}'
        for name, dtype in UNIFIED_SCHEMA.items()
    )
    return f"CREATE TABLE {table_name} ({columns_sql});"


def _build_insert_select_sql(temp_table: str, existing_columns: set[str]) -> str:
    """Prepare the SELECT statement to copy and transform data."""
    column_names = [f'"{name}"' for name in UNIFIED_SCHEMA]
    select_expressions = []
    for name in UNIFIED_SCHEMA:
        if name in existing_columns:
            select_expressions.append(f'"{name}"')
        elif name == "doc_type":
            select_expressions.append("'note' AS doc_type")
        elif name == "status":
            select_expressions.append("'draft' AS status")
        else:
            select_expressions.append(f'NULL AS "{name}"')

    select_sql = f"SELECT {', '.join(select_expressions)} FROM documents"
    return f"INSERT INTO {temp_table} ({', '.join(column_names)}) {select_sql};"


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
    conn.execute(f"ALTER TABLE {temp_table_name} RENAME TO documents;")


def migrate_journals_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Applies the CHECK constraint (window_end >= window_start) to 'journals'.

    This uses the 'create-copy-swap' strategy since DuckDB doesn't support
    adding constraints to existing tables.
    """
    # 1. Check if table exists
    tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
    if "journals" not in tables:
        return

    # 2. Check if constraint already exists (naive check via trying to trigger it?
    # Or just re-apply migration which is safer).
    # Since we can't easily check for constraint existence in DuckDB metadata
    # for CHECK constraints in a portable way without parsing SQL,
    # we'll use a pragmatic approach: The migration is "idempotent enough"
    # if we just re-create the table. But for large data this is slow.
    # For now, let's assume we always want to ensure the constraint.

    temp_table = "journals_migration_temp"

    # Drop temp table if exists from failed run
    conn.execute(f"DROP TABLE IF EXISTS {temp_table}")

    # 3. Create new table with constraints
    # We use the schema definition + constraint logic manually or via helper
    from egregora.database.schemas import (
        JOURNALS_SCHEMA,
        create_table_if_not_exists,
        get_table_check_constraints,
    )

    # We need an Ibis schema to use create_table_if_not_exists, but here we have raw connection.
    # The helper handles raw connection too.
    constraints = get_table_check_constraints("journals")

    # We pass overwrite=True to create the temp table
    create_table_if_not_exists(
        conn, temp_table, JOURNALS_SCHEMA, overwrite=True, check_constraints=constraints
    )

    # 4. Copy data
    # We assume columns match. If schema changed, we'd need explicit column mapping.
    # JOURNALS_SCHEMA keys are the columns.
    columns = ", ".join(f'"{col}"' for col in JOURNALS_SCHEMA.names)

    try:
        conn.execute(f"INSERT INTO {temp_table} ({columns}) SELECT {columns} FROM journals")
    except duckdb.ConstraintException as e:
        logger.error(f"Migration failed: Existing data violates new constraints: {e}")
        # Cleanup and re-raise or handle
        conn.execute(f"DROP TABLE {temp_table}")
        raise

    # 5. Swap
    conn.execute("DROP TABLE journals")
    conn.execute(f"ALTER TABLE {temp_table} RENAME TO journals")
    logger.info("Successfully migrated 'journals' table with new constraints.")
