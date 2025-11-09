"""Database utilities and schemas for Egregora."""

from egregora.database.connection import duckdb_backend
from egregora.database.message_schema import MESSAGE_SCHEMA
from egregora.database.runs_schema import (
    RUNS_TABLE_DDL,
    RUNS_TABLE_SCHEMA,
    create_runs_table,
    ensure_runs_table_exists,
)
from egregora.database.storage import StorageManager, temp_storage

__all__ = [
    "MESSAGE_SCHEMA",
    "RUNS_TABLE_DDL",
    "RUNS_TABLE_SCHEMA",
    "StorageManager",
    "create_runs_table",
    "duckdb_backend",
    "ensure_runs_table_exists",
    "temp_storage",
]
