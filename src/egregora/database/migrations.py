"""Schema Migration Script."""

import logging

import duckdb

# Import the target schema and the type conversion utility
from egregora.database.schemas import UNIFIED_SCHEMA, ibis_to_duckdb_type, get_table_check_constraints
from egregora.database.utils import quote_identifier

logger = logging.getLogger(__name__)


def _get_existing_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    """Get the existing columns from a table."""
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {row[1] for row in result}


def _has_check_constraints(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    """Check if the table has any CHECK constraints."""
    try:
        # duckdb_constraints() returns info about constraints
        res = conn.execute(
            f"SELECT count(*) FROM duckdb_constraints() WHERE table_name='{table_name}' AND constraint_type='CHECK'"
        ).fetchone()
        return res[0] > 0
    except duckdb.Error:
        # Fallback if system table is unavailable or changed
        return False


def _build_documents_create_table_sql(table_name: str) -> str:
    """Define the new schema with NOT NULL constraints and CHECK constraints."""
    columns_sql = ", ".join(
        f'{quote_identifier(name)} {ibis_to_duckdb_type(dtype)}{" NOT NULL" if not dtype.nullable else ""}'
        for name, dtype in UNIFIED_SCHEMA.items()
    )

    check_constraints = get_table_check_constraints("documents")
    constraint_clauses = []
    for constraint_name, check_expr in check_constraints.items():
        constraint_clauses.append(
            f"CONSTRAINT {quote_identifier(constraint_name)} CHECK ({check_expr})"
        )

    all_clauses = [columns_sql]
    if constraint_clauses:
        all_clauses.extend(constraint_clauses)

    return f"CREATE TABLE {quote_identifier(table_name)} ({', '.join(all_clauses)});"


def _build_documents_insert_select_sql(temp_table: str, existing_columns: set[str]) -> str:
    """Prepare the SELECT statement to copy and transform data."""
    column_names = [f'{quote_identifier(name)}' for name in UNIFIED_SCHEMA]
    select_expressions = []
    for name in UNIFIED_SCHEMA:
        if name in existing_columns:
            select_expressions.append(f'{quote_identifier(name)}')
        elif name == "doc_type":
            select_expressions.append("'note' AS doc_type")
        elif name == "status":
            select_expressions.append("'draft' AS status")
        else:
            select_expressions.append(f'NULL AS {quote_identifier(name)}')

    select_sql = f"SELECT {', '.join(select_expressions)} FROM documents"
    return f"INSERT INTO {quote_identifier(temp_table)} ({', '.join(column_names)}) {select_sql};"


def migrate_documents_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Applies the Pure UNIFIED_SCHEMA to an existing 'documents' table.

    This migration is idempotent and robustly handles NOT NULL constraints
    by creating a new table, copying data, and replacing the old table.
    """
    existing_columns = _get_existing_columns(conn, "documents")
    has_constraints = _has_check_constraints(conn, "documents")

    # Check if migration is needed
    # If we have all columns AND we have constraints, we skip.
    # Note: precise constraint matching is hard, so we assume if ANY check constraint exists, it's migrated.
    if "doc_type" in existing_columns and "status" in existing_columns and has_constraints:
        logger.info("Schema is already up to date. No migration needed.")
        return

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
