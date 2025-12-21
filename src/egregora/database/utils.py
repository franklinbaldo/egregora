"""Database utility functions."""

import contextlib
from pathlib import Path

import duckdb


def quote_identifier(identifier: str) -> str:
    """Quote a SQL identifier to prevent injection and handle special characters.

    Args:
        identifier: The identifier to quote (table name, column name, etc.)

    Returns:
        Properly quoted identifier safe for use in SQL

    Note:
        DuckDB uses double quotes for identifiers. Inner quotes are escaped by doubling.
        Example: my"table → "my""table"

    """
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


class SimpleDuckDBStorage:
    """Minimal DuckDB storage for CLI read commands without initializing Ibis.

    This lightweight storage class is used by CLI commands like `top` and
    `show reader-history` that need to query the DuckDB database without
    the overhead of initializing the full Ibis-based storage infrastructure.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = duckdb.connect(str(db_path))

    @contextlib.contextmanager
    def connection(self) -> contextlib.AbstractContextManager[duckdb.DuckDBPyConnection]:
        yield self._conn

    def execute_query(self, sql: str, params: list | None = None) -> list[tuple]:
        return self._conn.execute(sql, params or []).fetchall()

    def execute_query_single(self, sql: str, params: list | None = None) -> tuple | None:
        return self._conn.execute(sql, params or []).fetchone()

    def get_table_columns(self, table_name: str) -> set[str]:
        info = self._conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        return {row[1] for row in info}


def get_simple_storage(db_path: Path) -> SimpleDuckDBStorage:
    """Get a simple DuckDB storage instance for CLI queries.

    Args:
        db_path: Path to the DuckDB database file

    Returns:
        SimpleDuckDBStorage instance for executing queries

    Note:
        This is used by CLI read commands that don't need the full Ibis stack.

    """
    return SimpleDuckDBStorage(db_path)
