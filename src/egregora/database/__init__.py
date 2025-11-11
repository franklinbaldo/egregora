"""Database utilities and schemas for Egregora.

Phase 2.2: Centralized database management.
- All schemas consolidated in schemas.py
- Connection utilities consolidated in storage.py
"""

from egregora.database.schemas import (
    CONVERSATION_SCHEMA,
    MESSAGE_SCHEMA,
    RUNS_TABLE_DDL,
    RUNS_TABLE_SCHEMA,
    WHATSAPP_CONVERSATION_SCHEMA,
    create_runs_table,
    ensure_runs_table_exists,
)
from egregora.database.storage import StorageManager, duckdb_backend, temp_storage

__all__ = [
    # Schemas
    "CONVERSATION_SCHEMA",
    "MESSAGE_SCHEMA",
    "RUNS_TABLE_DDL",
    "RUNS_TABLE_SCHEMA",
    "WHATSAPP_CONVERSATION_SCHEMA",
    # Connection utilities
    "StorageManager",
    # Runs table utilities
    "create_runs_table",
    "duckdb_backend",
    "ensure_runs_table_exists",
    "temp_storage",
]
