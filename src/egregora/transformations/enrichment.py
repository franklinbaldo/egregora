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
    messages_table_filtered = messages_table.select(*schema.names)

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
        normalized_rows = [{column: row.get(column) for column in schema.names} for row in new_rows]
        enrichment_table = ibis.memtable(normalized_rows).cast(schema)
        combined = messages_table_filtered.union(enrichment_table, distinct=False)

        sort_col = "ts" if "ts" in schema.names else "timestamp"
        combined = combined.order_by(sort_col)
    else:
        combined = messages_table_filtered

    return combined


__all__ = ["combine_with_enrichment_rows"]
