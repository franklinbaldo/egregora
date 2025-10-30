"""Utilities for managing DuckDB schema and raw SQL helpers."""

from __future__ import annotations

from importlib import resources
from textwrap import dedent
from typing import Iterable, Protocol


class SupportsRawSQL(Protocol):
    """Protocol for objects exposing a ``raw_sql`` method."""

    def raw_sql(self, query: str) -> object: ...


class SupportsExecute(Protocol):
    """Protocol for objects exposing an ``execute`` method."""

    def execute(self, query: str) -> object: ...


def quote_identifier(name: str) -> str:
    """Return ``name`` quoted for safe inclusion in DuckDB SQL."""

    if not name:
        raise ValueError("Identifier must not be empty")
    return '"' + name.replace('"', '""') + '"'


def string_literal(value: str) -> str:
    """Return ``value`` quoted as a SQL string literal."""

    return "'" + value.replace("'", "''") + "'"


def load_schema_sql() -> str:
    """Load the central schema SQL file bundled with the package."""

    return resources.files("egregora").joinpath("schema.sql").read_text()


def apply_schema(connection: SupportsExecute) -> None:
    """Execute the bundled schema SQL against ``connection``."""

    sql = load_schema_sql()
    statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
    for statement in statements:
        connection.execute(statement)


def create_index_if_not_exists(
    backend: SupportsRawSQL,
    *,
    index_name: str,
    table_name: str,
    columns: Iterable[str],
) -> None:
    """Create an index if missing using the DuckDB backend."""

    column_sql = ", ".join(quote_identifier(column) for column in columns)
    backend.raw_sql(
        dedent(
            f"""
            CREATE INDEX IF NOT EXISTS {quote_identifier(index_name)}
            ON {quote_identifier(table_name)} ({column_sql})
            """
        )
    )


def drop_index_if_exists(backend: SupportsRawSQL, *, index_name: str) -> None:
    """Drop an index if it exists."""

    backend.raw_sql(
        dedent(
            f"""
            DROP INDEX IF EXISTS {quote_identifier(index_name)}
            """
        )
    )


def drop_table_if_exists(backend: SupportsRawSQL, *, table_name: str) -> None:
    """Drop a table if it exists."""

    backend.raw_sql(
        dedent(
            f"""
            DROP TABLE IF EXISTS {quote_identifier(table_name)}
            """
        )
    )


def create_vss_index(
    backend: SupportsRawSQL,
    *,
    index_name: str,
    table_name: str,
) -> None:
    """Create a DuckDB VSS index for the ``embedding`` column."""

    backend.raw_sql(
        dedent(
            f"""
            CREATE INDEX {quote_identifier(index_name)}
            ON {quote_identifier(table_name)} (embedding)
            USING vss(metric='cosine', storage_type='ivfflat')
            """
        )
    )
