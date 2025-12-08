"""Database utilities, schemas, and infrastructure for Egregora.

This package consolidates all persistence, state management, and infrastructure:
- Schemas: IR schema definitions
- Storage: DuckDB connection management
- Streaming: Memory-efficient data access utilities
- Tracking: Run observability and lineage
- Views: Common transformations for downstream consumers

**Philosophy**: Centralized infrastructure for state and side effects.
"""

from egregora.database import ir_schema as schemas
from egregora.database.duckdb_manager import DuckDBStorageManager, duckdb_backend, temp_storage
from egregora.database.init import initialize_database
from egregora.database.ir_schema import RUNS_TABLE_SCHEMA, create_runs_table, ensure_runs_table_exists
from egregora.database.streaming import (
    copy_expr_to_ndjson,
    copy_expr_to_parquet,
    ensure_deterministic_order,
    stream_ibis,
)
from egregora.database.tracking import (
    RunContext,
    get_git_commit_sha,
    record_lineage,
    record_run,
    run_stage_with_tracking,
)
from egregora.database.views import (
    COMMON_VIEWS,
    ViewBuilder,
    chunks_sql,
    chunks_view,
    daily_aggregates_view,
    get_view_builder,
    hourly_aggregates_view,
    list_common_views,
    messages_with_media_view,
    messages_with_text_view,
)

__all__ = [
    # Views
    "COMMON_VIEWS",
    # Schemas
    "RUNS_TABLE_SCHEMA",
    # Storage
    "DuckDBStorageManager",
    # Tracking & Observability
    "RunContext",
    "ViewBuilder",
    "chunks_sql",
    "chunks_view",
    # Streaming
    "copy_expr_to_ndjson",
    "copy_expr_to_parquet",
    # Runs table utilities
    "create_runs_table",
    "daily_aggregates_view",
    "duckdb_backend",
    "ensure_deterministic_order",
    "ensure_runs_table_exists",
    "get_git_commit_sha",
    "get_view_builder",
    "hourly_aggregates_view",
    # Initialization
    "initialize_database",
    "list_common_views",
    "messages_with_media_view",
    "messages_with_text_view",
    "record_lineage",
    "record_run",
    "run_stage_with_tracking",
    "schemas",
    "stream_ibis",
    "temp_storage",
]
