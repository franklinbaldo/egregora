"""Enrichment transformation utilities.

This module contains utility functions for combining and transforming
enriched message data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import ibis

if TYPE_CHECKING:
    from ibis.expr.types import Table


def combine_with_enrichment_rows(
    messages_table: Table,
    new_rows: list[dict],
    schema: ibis.Schema,
) -> Table:
    """Combine a base messages table with new enrichment rows.

    Args:
        messages_table: Base table of messages
        new_rows: List of enrichment rows to add
        schema: Schema to apply to the combined table

    Returns:
        Combined table with schema applied

    """
    # Add any missing columns from the schema as nulls
    mutations = {
        col_name: ibis.null().cast(col_type)
        for col_name, col_type in schema.items()
        if col_name not in messages_table.columns
    }
    messages_with_all_cols = messages_table.mutate(**mutations) if mutations else messages_table

    messages_table_filtered = messages_with_all_cols.select(*schema.names)

    # Ensure timestamps are UTC
    if "ts" in messages_table_filtered.columns:
        messages_table_filtered = messages_table_filtered.mutate(
            ts=messages_table_filtered.ts.cast("timestamp('UTC')")
        )
    elif "timestamp" in messages_table_filtered.columns:
        messages_table_filtered = messages_table_filtered.mutate(
            timestamp=messages_table_filtered.timestamp.cast("timestamp('UTC', 9)")
        )

    messages_table_filtered = messages_table_filtered.cast(schema)

    if new_rows:
        # Create memtable from rows (infer schema from present data)
        enrichment_table = ibis.memtable(new_rows)

        # Identify missing columns and add them as explicit NULLs
        # This prevents PyArrow errors when converting sparse data (e.g. missing timestamps)
        missing_cols = {
            col: ibis.null().cast(dtype)
            for col, dtype in schema.items()
            if col not in enrichment_table.columns
        }

        if missing_cols:
            enrichment_table = enrichment_table.mutate(**missing_cols)

        # Select only schema columns (drops extras) and cast to ensure types
        enrichment_table = enrichment_table.select(schema.names).cast(schema)

        combined = messages_table_filtered.union(enrichment_table, distinct=False)

        sort_col = "ts" if "ts" in schema.names else "timestamp"
        combined = combined.order_by(sort_col)
    else:
        combined = messages_table_filtered

    return combined


__all__ = ["combine_with_enrichment_rows"]
