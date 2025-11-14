"""Database utilities, schemas, and infrastructure for Egregora.

This package consolidates all persistence, state management, and infrastructure:
- Schemas: IR schema definitions and validation
- Storage: DuckDB connection management
- Streaming: Memory-efficient data access utilities
- Tracking: Run observability and lineage
- Views: Transformation registry

**Philosophy**: Centralized infrastructure for state, side effects, and registries.
"""

from egregora.database.duckdb_manager import DuckDBStorageManager, duckdb_backend, temp_storage
from egregora.database.ir_schema import (
    CONVERSATION_SCHEMA,
    MESSAGE_SCHEMA,
    RUN_EVENTS_SCHEMA,
    RUNS_TABLE_DDL,
    RUNS_TABLE_SCHEMA,
    WHATSAPP_CONVERSATION_SCHEMA,
    create_runs_table,
    ensure_runs_table_exists,
)
from egregora.database.streaming import (
    copy_expr_to_ndjson,
    copy_expr_to_parquet,
    ensure_deterministic_order,
    stream_ibis,
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
    "RUN_EVENTS_SCHEMA",
    "WHATSAPP_CONVERSATION_SCHEMA",
    # Storage
    "DuckDBStorageManager",
    # Streaming
    "copy_expr_to_ndjson",
    "copy_expr_to_parquet",
    "ensure_deterministic_order",
    "stream_ibis",
    # Tracking & Observability
    "RunContext",
    # View Registry
    "ViewBuilder",
    "ViewRegistry",
    # Runs table utilities
    "create_runs_table",
    "duckdb_backend",
    "ensure_runs_table_exists",
    "fingerprint_table",
    "get_git_commit_sha",
    "record_lineage",
    "record_run",
    "run_stage_with_tracking",
    "temp_storage",
    "views",
]
