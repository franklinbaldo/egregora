"""Egregora database layer.

This package provides a unified interface for data persistence and retrieval,
abstracting away the underlying storage technology (e.g., DuckDB, LanceDB).

Key modules:
- :module:`duckdb_manager`: Centralized DuckDB connection and lifecycle management.
- :module:`ir_schema`: Ibis schemas for intermediate representations (IR) of data.
- :module:`protocols`: Abstract protocols for storage interfaces.
- :module:`run_store`: Data access layer for pipeline run history.
- :module:`sql`: SQL query rendering and management.
- :module:`streaming`: Utilities for streaming data from storage.
- :module:`tracking`: Pipeline run tracking with observability and lineage.
- :module:`utils`: Shared database utilities.
"""

from egregora.database import ir_schema as schemas
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.protocols import StorageProtocol
from egregora.database.run_store import RunStore
from egregora.database.streaming import stream_ibis
from egregora.database.tracking import (
    RunContext,
    record_lineage,
    run_stage_with_tracking,
)
from egregora.database.utils import quote_identifier

__all__ = [
    "DuckDBStorageManager",
    "quote_identifier",
    "record_lineage",
    "RunContext",
    "run_stage_with_tracking",
    "RunStore",
    "schemas",
    "StorageProtocol",
    "stream_ibis",
]
