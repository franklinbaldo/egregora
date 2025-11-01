"""Canonical batching utilities for Ibis tables.

Provides a simple, deterministic way to iterate over table rows in batches
using offset-based pagination instead of row_number windowing.

Benefits over row_number approach:
- Simpler mental model (no temporary columns)
- More DuckDB optimizer friendly
- Cleaner code (no column pollution)
- Easier to test and reason about
"""

from collections.abc import Iterator
from typing import Any

from ibis.expr.types import Table


def batch_table(
    table: Table,
    batch_size: int,
    order_by: list[str] | None = None,
) -> Iterator[Table]:
    """
    Yield batches of table using stable ordering and offset pagination.

    Args:
        table: Ibis table to batch
        batch_size: Number of rows per batch
        order_by: Column names to order by. If None, attempts to infer
                 stable ordering from common timestamp/id columns.

    Yields:
        Table slices of size batch_size (last batch may be smaller)

    Example:
        >>> for batch in batch_table(messages, batch_size=100, order_by=["timestamp"]):
        ...     process_batch(batch)
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")

    # Infer ordering if not provided
    if order_by is None:
        order_by = _infer_stable_ordering(table)

    if not order_by:
        raise ValueError(
            "Cannot determine stable ordering. "
            "Provide order_by parameter or ensure table has "
            "timestamp/id columns."
        )

    # Apply ordering once
    ordered_table = table.order_by(order_by)

    offset = 0
    while True:
        # Get batch using limit + offset
        batch = ordered_table.limit(batch_size, offset=offset)

        # Execute to check if batch is empty
        # (more efficient than count() for each batch)
        batch_result = batch.execute()

        if len(batch_result) == 0:
            break

        # Yield the batch expression (not the executed result)
        # This allows downstream code to further transform if needed
        yield batch

        offset += batch_size


def batch_table_to_records(
    table: Table,
    batch_size: int = 1000,
    order_by: list[str] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """
    Yield batches of table rows as dictionaries.

    Convenience wrapper around batch_table() that executes and converts
    each batch to a list of dicts.

    Args:
        table: Ibis table to batch
        batch_size: Number of rows per batch
        order_by: Column names to order by

    Yields:
        List of dictionaries, one per row in batch

    Example:
        >>> for records in batch_table_to_records(messages, batch_size=100):
        ...     for record in records:
        ...         print(record["message"])
    """
    for batch in batch_table(table, batch_size=batch_size, order_by=order_by):
        # Execute batch and convert to records
        result = batch.execute()

        # Handle different result types (pandas DataFrame, pyarrow Table, etc.)
        if hasattr(result, "to_dict"):
            # pandas DataFrame
            records = result.to_dict("records")
        elif hasattr(result, "to_pylist"):
            # pyarrow Table
            records = result.to_pylist()
        elif hasattr(result, "to_pydict"):
            # DuckDB relation
            pydict = result.to_pydict()
            # Convert columnar dict to row dicts
            records = [
                {col: pydict[col][i] for col in pydict}
                for i in range(len(next(iter(pydict.values()))))
            ]
        else:
            # Fallback: assume iterable of dict-like objects
            records = [dict(row) for row in result]

        yield records


# Common timestamp/id column names for stable ordering inference
_STABLE_ORDER_CANDIDATES: tuple[str, ...] = (
    "timestamp",
    "created_at",
    "datetime",
    "date",
    "ts",
    "time",
    "message_id",
    "id",
    "uuid",
    "key",
)


def _infer_stable_ordering(table: Table) -> list[str]:
    """
    Infer a stable ordering for table based on common column patterns.

    Returns:
        List of column names to use for ordering, or empty list if unable to infer.
    """
    columns = set(table.columns)

    # Try common timestamp/id columns in priority order
    for candidate in _STABLE_ORDER_CANDIDATES:
        if candidate in columns:
            return [candidate]

    # Fallback: use all columns (stable but arbitrary)
    # This ensures deterministic batching even for ad-hoc tables
    if columns:
        return sorted(columns)

    return []
