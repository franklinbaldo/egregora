"""Database utilities, schemas, and infrastructure for Egregora.

This package consolidates all persistence, state management, and infrastructure:
- Schemas: IR schema definitions and validation
- Storage: DuckDB connection management
- Tracking: Run observability and lineage
- Views: Transformation registry

**Philosophy**: Centralized infrastructure for state, side effects, and registries.

"""

from egregora.database.duckdb_manager import DuckDBStorageManager, duckdb_backend, temp_storage
from egregora.database.ir_schema import (
    CONVERSATION_SCHEMA,
    MESSAGE_SCHEMA,
    RUNS_TABLE_DDL,
    RUNS_TABLE_SCHEMA,
    WHATSAPP_CONVERSATION_SCHEMA,
    create_runs_table,
    ensure_runs_table_exists,
)
from egregora.database.tracking import (
    RunContext,
    fingerprint_table,
    get_git_commit_sha,
    record_lineage,
    record_run,
    run_stage_with_tracking,
)
from egregora.database.views import ViewBuilder, ViewRegistry, views

__all__ = [
    # Schemas
    "CONVERSATION_SCHEMA",
    "MESSAGE_SCHEMA",
    "RUNS_TABLE_DDL",
    "RUNS_TABLE_SCHEMA",
    "WHATSAPP_CONVERSATION_SCHEMA",
    # Storage
    "DuckDBStorageManager",
    "duckdb_backend",
    "temp_storage",
    # Runs table utilities
    "create_runs_table",
    "ensure_runs_table_exists",
    # Tracking & Observability
    "RunContext",
    "fingerprint_table",
    "get_git_commit_sha",
    "record_lineage",
    "record_run",
    "run_stage_with_tracking",
    # View Registry
    "ViewBuilder",
    "ViewRegistry",
    "views",
]
