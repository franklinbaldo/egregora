"""Database utilities, schemas, and infrastructure for Egregora.

This package consolidates all persistence, state management, and infrastructure:
- Schemas: Schema definitions
- Storage: DuckDB connection management
- Streaming: Memory-efficient data access utilities
- Views: Common transformations for downstream consumers

**Philosophy**: Centralized infrastructure for state and side effects.
"""

from egregora.database import schemas
from egregora.database.duckdb_manager import (
    DuckDBStorageManager,
    duckdb_backend,
    temp_storage,
)
from egregora.database.init import initialize_database
from egregora.database.streaming import (
    copy_expr_to_ndjson,
    copy_expr_to_parquet,
    ensure_deterministic_order,
    stream_ibis,
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
    "schemas",
    # Storage
    "DuckDBStorageManager",
    "ViewBuilder",
    "chunks_sql",
    "chunks_view",
    # Streaming
    "copy_expr_to_ndjson",
    "copy_expr_to_parquet",
    "daily_aggregates_view",
    "duckdb_backend",
    "ensure_deterministic_order",
    "get_view_builder",
    "hourly_aggregates_view",
    # Initialization
    "initialize_database",
    "list_common_views",
    "messages_with_media_view",
    "messages_with_text_view",
    "stream_ibis",
    "temp_storage",
]
