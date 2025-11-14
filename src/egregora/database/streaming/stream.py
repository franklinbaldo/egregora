"""Streaming and I/O utilities for Ibis expressions using DuckDB.

This module provides memory-efficient streaming and file output operations
for Ibis expressions, avoiding full materialization to pandas/PyArrow.

Core Principles:
1. Never call .execute() (returns pandas DataFrame)
2. Never call .to_pyarrow() on large tables
3. Stream via DuckDB's native fetch API
4. Use COPY ... TO for file outputs (zero Python overhead)

Usage:
    >>> import ibis
    >>> from egregora.database.streaming import stream_ibis
    >>>
    >>> # Stream large table in batches
    >>> for batch in stream_ibis(expr, con, batch_size=1000):
    >>>     for row in batch:
    >>>         process(row)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    import duckdb
    import ibis
    from ibis.backends.duckdb import Backend as DuckDBBackend


def _get_duckdb_connection(con: DuckDBBackend) -> duckdb.DuckDBPyConnection:
    """Extract the underlying DuckDB connection from Ibis backend.

    Args:
        con: Ibis DuckDB backend connection

    Returns:
        The native DuckDB connection object

    Raises:
        AttributeError: If connection doesn't expose DuckDB API

    """
    if not hasattr(con, "con"):
        msg = f"Backend {type(con).__name__} doesn't expose DuckDB connection. stream_ibis requires ibis.duckdb backend."
        raise AttributeError(msg)
    return con.con


def stream_ibis(
    expr: ibis.Expr, con: DuckDBBackend, batch_size: int = 1000
) -> Iterable[list[dict[str, Any]]]:
    """Stream Ibis expression rows in batches without full materialization.

    This uses DuckDB's native fetchmany() API to avoid loading the entire
    result set into memory. Works correctly with tables in the Ibis
    connection's context (no "table not found" errors).

    Args:
        expr: Ibis table expression to stream
        con: Ibis DuckDB backend connection
        batch_size: Number of rows per batch (default: 1000)

    Yields:
        Lists of dictionaries, where each dict is a row

    Example:
        >>> expr = table.filter(table.active == True).select("id", "name")
        >>> for batch in stream_ibis(expr, con, batch_size=500):
        >>>     print(f"Processing {len(batch)} rows")
        >>>     for row in batch:
        >>>         print(row["name"])

    Note:
        For deterministic results, use ensure_deterministic_order() first:
        >>> expr = ensure_deterministic_order(expr)
        >>> for batch in stream_ibis(expr, con):
        >>>     ...

    """
    duckdb_con = _get_duckdb_connection(con)
    sql = con.compile(expr)
    rel = duckdb_con.sql(sql)
    cols = rel.columns
    while True:
        rows = rel.fetchmany(batch_size)
        if not rows:
            break
        batch = [dict(zip(cols, row, strict=False)) for row in rows]
        yield batch


def copy_expr_to_parquet(expr: ibis.Expr, con: DuckDBBackend, path: str | Path) -> None:
    """Write Ibis expression directly to Parquet file using DuckDB COPY.

    This is the most efficient way to export Ibis expressions - zero Python
    overhead, no materialization. DuckDB writes the file directly.

    Args:
        expr: Ibis expression to write
        con: Ibis DuckDB backend connection
        path: Output file path

    Example:
        >>> expr = table.filter(table.year == 2025)
        >>> copy_expr_to_parquet(expr, con, "output/2025.parquet")

    Note:
        The output directory must exist. DuckDB will create the file.

    """
    duckdb_con = _get_duckdb_connection(con)
    sql = con.compile(expr)
    safe_path = str(path).replace("'", "''")
    copy_sql = f"COPY ({sql}) TO '{safe_path}' (FORMAT parquet)"
    duckdb_con.execute(copy_sql)


def copy_expr_to_ndjson(expr: ibis.Expr, con: DuckDBBackend, path: str | Path) -> None:
    """Write Ibis expression directly to newline-delimited JSON file.

    Uses DuckDB COPY for efficient writing without materialization.

    Args:
        expr: Ibis expression to write
        con: Ibis DuckDB backend connection
        path: Output file path

    Example:
        >>> expr = table.select("id", "message", "timestamp")
        >>> copy_expr_to_ndjson(expr, con, "messages.ndjson")

    Note:
        Output format is newline-delimited JSON (one JSON object per line).

    """
    duckdb_con = _get_duckdb_connection(con)
    sql = con.compile(expr)
    safe_path = str(path).replace("'", "''")
    copy_sql = f"COPY ({sql}) TO '{safe_path}' (FORMAT json)"
    duckdb_con.execute(copy_sql)


def ensure_deterministic_order(expr: ibis.Expr) -> ibis.Expr:
    """Sort Ibis expression by canonical keys for reproducible iteration.

    Egregora's pipeline requires deterministic ordering for:
    - Reproducible test outputs
    - Stable enrichment batching
    - Consistent RAG indexing

    This function sorts by common key columns if they exist:
    1. published_at (timestamp)
    2. id (identifier)

    Args:
        expr: Ibis expression to sort

    Returns:
        Sorted expression (or original if no sortable columns found)

    Example:
        >>> expr = ensure_deterministic_order(table)
        >>> for batch in stream_ibis(expr, con):
        >>>     # Guaranteed stable order across runs
        >>>     process(batch)

    Note:
        If your table has different key columns, call .order_by() directly:
        >>> expr = table.order_by("timestamp", "message_id")

    """
    schema = expr.schema()
    sortable_columns = [col for col in ["published_at", "timestamp", "id"] if col in schema.names]
    if sortable_columns:
        return expr.order_by(sortable_columns)
    return expr
