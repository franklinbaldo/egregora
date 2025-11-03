"""Streaming utilities for Egregora - Ibis-first streaming and I/O.

This module provides utilities for working with Ibis expressions and DuckDB
without materializing full tables into pandas/PyArrow. All utilities enforce
the "Ibis-first" architecture principle.

Public API:
    - stream_ibis: Stream Ibis expression rows in batches
    - copy_expr_to_parquet: Write Ibis expression directly to Parquet
    - copy_expr_to_ndjson: Write Ibis expression directly to NDJSON
    - ensure_deterministic_order: Sort expression for reproducible iteration
"""

from egregora.streaming.stream import (
    copy_expr_to_ndjson,
    copy_expr_to_parquet,
    ensure_deterministic_order,
    stream_ibis,
)

__all__ = [
    "stream_ibis",
    "copy_expr_to_parquet",
    "copy_expr_to_ndjson",
    "ensure_deterministic_order",
]
