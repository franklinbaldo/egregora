"""Schema Migration Script."""

import logging

import duckdb

# Import the target schema and the type conversion utility
from egregora.database.schemas import (
    INGESTION_MESSAGE_SCHEMA,
    TASKS_SCHEMA,
    UNIFIED_SCHEMA,
    ibis_to_duckdb_type,
)

logger = logging.getLogger(__name__)


def _get_existing_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    """Get the existing columns from a table."""
    try:
        result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        return {row[1] for row in result}
    except duckdb.Error:
        return set()


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    """Check if a table exists."""
    try:
        conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        return True
    except duckdb.Error:
        return False


def _has_primary_key(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    """Check if a table has a primary key."""
    try:
        constraints = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        # The 'pk' column (index 5) is non-zero for primary key columns
        return any(row[5] > 0 for row in constraints)
    except duckdb.Error:
        return False


def migrate_documents_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Applies the UNIFIED_SCHEMA with a primary key to the 'documents' table."""
    if not _table_exists(conn, "documents"):
        logger.info("Documents table does not exist. Creating it with primary key.")
        columns_sql = ", ".join(
            f'"{name}" {ibis_to_duckdb_type(dtype)}{" NOT NULL" if not dtype.nullable else ""}'
            for name, dtype in UNIFIED_SCHEMA.items()
        )
        create_sql = f"CREATE TABLE documents ({columns_sql}, PRIMARY KEY(id));"
        conn.execute(create_sql)
        return

    if _has_primary_key(conn, "documents"):
        logger.info("Documents table already has a primary key. Skipping migration.")
        return

    logger.info("Applying migration to 'documents' table to add primary key...")
    temp_table_name = "documents_temp"
    existing_columns = _get_existing_columns(conn, "documents")

    # Build CREATE TABLE with PRIMARY KEY
    columns_sql = ", ".join(
        f'"{name}" {ibis_to_duckdb_type(dtype)}{" NOT NULL" if not dtype.nullable else ""}'
        for name, dtype in UNIFIED_SCHEMA.items()
    )
    create_sql = f"CREATE TABLE {temp_table_name} ({columns_sql}, PRIMARY KEY(id));"
    conn.execute(create_sql)

    # Build INSERT SELECT to copy data
    column_names = ", ".join(f'"{name}"' for name in UNIFIED_SCHEMA)
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
    insert_sql = f"INSERT INTO {temp_table_name} ({column_names}) {select_sql};"
    conn.execute(insert_sql)

    # Swap tables
    conn.execute("DROP TABLE documents;")
    conn.execute(f"ALTER TABLE {temp_table_name} RENAME TO documents;")
    logger.info("✓ Successfully migrated 'documents' table.")


def _add_primary_key_migration(
    conn: duckdb.DuckDBPyConnection, table_name: str, schema: dict, pk_column: str
) -> None:
    """Generic helper to add a primary key to a table using a safe migration."""
    if not _table_exists(conn, table_name):
        logger.info(f"{table_name.capitalize()} table does not exist. Creating it with primary key.")
        columns_sql = ", ".join(
            f'"{name}" {ibis_to_duckdb_type(dtype)}{" NOT NULL" if not dtype.nullable else ""}'
            for name, dtype in schema.items()
        )
        create_sql = f"CREATE TABLE {table_name} ({columns_sql}, PRIMARY KEY({pk_column}));"
        conn.execute(create_sql)
        return

    if _has_primary_key(conn, table_name):
        logger.info(f"{table_name.capitalize()} table already has a primary key. Skipping migration.")
        return

    logger.info(f"Applying migration to '{table_name}' table to add primary key...")
    temp_table_name = f"{table_name}_temp"

    columns_sql = ", ".join(
        f'"{name}" {ibis_to_duckdb_type(dtype)}{" NOT NULL" if not dtype.nullable else ""}'
        for name, dtype in schema.items()
    )
    create_sql = f"CREATE TABLE {temp_table_name} ({columns_sql}, PRIMARY KEY({pk_column}));"
    conn.execute(create_sql)

    existing_columns = ", ".join(f'"{col}"' for col in schema)
    insert_sql = (
        f"INSERT INTO {temp_table_name} ({existing_columns}) SELECT {existing_columns} FROM {table_name};"
    )
    conn.execute(insert_sql)

    conn.execute(f"DROP TABLE {table_name};")
    conn.execute(f"ALTER TABLE {temp_table_name} RENAME TO {table_name};")
    logger.info(f"✓ Successfully migrated '{table_name}' table.")


def migrate_tasks_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Adds a primary key to the 'tasks' table if it doesn't exist."""
    _add_primary_key_migration(conn, "tasks", TASKS_SCHEMA, "task_id")


def migrate_messages_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Adds a primary key to the 'messages' table if it doesn't exist."""
    _add_primary_key_migration(conn, "messages", INGESTION_MESSAGE_SCHEMA, "event_id")
