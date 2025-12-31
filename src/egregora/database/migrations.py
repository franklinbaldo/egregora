"""V3 Schema Migration Script."""
import duckdb
import logging
from ibis.expr import datatypes as dt

# Import the target schema and the type conversion utility
from egregora.database.schemas import UNIFIED_SCHEMA, ibis_to_duckdb_type

logger = logging.getLogger(__name__)

def migrate_documents_table(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Applies the V3 UNIFIED_SCHEMA to an existing 'documents' table.

    This migration is idempotent and robustly handles NOT NULL constraints
    by creating a new table, copying data, and replacing the old table.
    """
    # Get the existing columns from the 'documents' table
    result = conn.execute("PRAGMA table_info('documents')").fetchall()
    existing_columns = {row[1] for row in result}

    # Check if migration is needed
    if "doc_type" in existing_columns and "status" in existing_columns:
        logger.info("Schema is already up to date. No migration needed.")
        return

    temp_table_name = "documents_temp"

    # Define the new schema with NOT NULL constraints where appropriate
    columns_sql = ", ".join(
        f'"{name}" {ibis_to_duckdb_type(dtype)}'
        f'{" NOT NULL" if not dtype.nullable else ""}'
        for name, dtype in UNIFIED_SCHEMA.items()
    )

    create_temp_table_sql = f"CREATE TABLE {temp_table_name} ({columns_sql});"
    logger.info(f"Creating temporary table: {create_temp_table_sql}")
    conn.execute(create_temp_table_sql)

    # Prepare the list of columns for the INSERT statement
    column_names = [f'"{name}"' for name in UNIFIED_SCHEMA.keys()]

    # Prepare the SELECT statement to copy and transform data
    select_expressions = []
    for name, dtype in UNIFIED_SCHEMA.items():
        if name in existing_columns:
            select_expressions.append(f'"{name}"')
        elif name == 'doc_type':
            select_expressions.append("'note' AS doc_type")
        elif name == 'status':
            select_expressions.append("'draft' AS status")
        else:
            select_expressions.append(f"NULL AS \"{name}\"")

    select_sql = f"SELECT {', '.join(select_expressions)} FROM documents"

    # Copy data from the old table to the new one
    insert_sql = (
        f"INSERT INTO {temp_table_name} ({', '.join(column_names)}) {select_sql};"
    )
    logger.info(f"Copying data to temporary table: {insert_sql}")
    conn.execute(insert_sql)

    # Drop the old table and rename the new one
    logger.info("Replacing old table with new one.")
    conn.execute("DROP TABLE documents;")
    conn.execute(f"ALTER TABLE {temp_table_name} RENAME TO documents;")
