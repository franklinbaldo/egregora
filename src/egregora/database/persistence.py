"""Database persistence utilities."""
from __future__ import annotations
import logging
import re
import uuid
from typing import TYPE_CHECKING
import ibis
from . import schemas
from .ir_schema import CONVERSATION_SCHEMA

if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)

def combine_with_enrichment_rows(
    messages_table: Table,
    new_rows: list[dict],
) -> Table:
    """Combines a base messages table with new enrichment rows."""
    schema = CONVERSATION_SCHEMA
    messages_table_filtered = messages_table.select(*schema.names)
    messages_table_filtered = messages_table_filtered.mutate(
        timestamp=messages_table_filtered.timestamp.cast("timestamp('UTC', 9)")
    ).cast(schema)

    if new_rows:
        normalized_rows = [{column: row.get(column) for column in schema.names} for row in new_rows]
        enrichment_table = ibis.memtable(normalized_rows).cast(schema)
        combined = messages_table_filtered.union(enrichment_table, distinct=False)
        combined = combined.order_by("timestamp")
    else:
        combined = messages_table_filtered

    return combined

def persist_to_duckdb(
    table: Table,
    duckdb_connection: DuckDBBackend,
    target_table: str,
) -> None:
    """Persists an Ibis table to a DuckDB table atomically."""
    if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", target_table):
        msg = "target_table must be a valid DuckDB identifier"
        raise ValueError(msg)

    schemas.create_table_if_not_exists(duckdb_connection, target_table, CONVERSATION_SCHEMA)
    quoted_table = schemas.quote_identifier(target_table)
    column_list = ", ".join(schemas.quote_identifier(col) for col in CONVERSATION_SCHEMA.names)
    temp_view = f"_egregora_persist_{uuid.uuid4().hex}"

    try:
        duckdb_connection.create_view(temp_view, table, overwrite=True)
        quoted_view = schemas.quote_identifier(temp_view)
        duckdb_connection.raw_sql("BEGIN TRANSACTION")
        try:
            duckdb_connection.raw_sql(f"DELETE FROM {quoted_table}")
            duckdb_connection.raw_sql(
                f"INSERT INTO {quoted_table} ({column_list}) SELECT {column_list} FROM {quoted_view}"
            )
            duckdb_connection.raw_sql("COMMIT")
        except Exception:
            logger.exception("Transaction failed during DuckDB persistence, rolling back")
            duckdb_connection.raw_sql("ROLLBACK")
            raise
    finally:
        duckdb_connection.drop_view(temp_view, force=True)
