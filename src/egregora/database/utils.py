"""Database utility functions."""

import contextlib
from pathlib import Path
from urllib.parse import urlparse

import duckdb
import ibis


def resolve_db_uri(uri: str, site_root: Path) -> str:
    """Resolve database URI relative to site root.

    Handles special relative path syntax for DuckDB:
    - duckdb:///./path -> site_root/path
    - duckdb:///path -> /path (absolute) or path (relative to CWD)

    Args:
        uri: The Ibis connection URI
        site_root: The root directory of the site

    Returns:
        Resolved absolute URI string

    """
    if not uri:
        return uri

    parsed = urlparse(uri)
    if parsed.scheme == "duckdb" and not parsed.netloc:
        path_value = parsed.path
        if path_value and path_value not in {"/:memory:", ":memory:", "memory", "memory:"}:
            fs_path: Path
            if path_value.startswith("/./"):
                fs_path = (site_root / Path(path_value[3:])).resolve()
            else:
                fs_path = Path(path_value).resolve()

            fs_path.parent.mkdir(parents=True, exist_ok=True)
            return f"duckdb://{fs_path}"

    return uri


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
        # Lightweight Ibis backend for read operations used by EloStore
        self.ibis_conn = ibis.duckdb.connect(database=str(db_path), read_only=False)

    @contextlib.contextmanager
    def connection(self) -> contextlib.AbstractContextManager[duckdb.DuckDBPyConnection]:
        yield self._conn

    def execute_query(self, sql: str, params: list | None = None) -> list[tuple]:
        return self._conn.execute(sql, params or []).fetchall()

    def execute_query_single(self, sql: str, params: list | None = None) -> tuple | None:
        return self._conn.execute(sql, params or []).fetchone()

    def get_table_columns(self, table_name: str) -> set[str]:
        # Sentinel: Fix SQL injection vulnerability by quoting the table name
        quoted_name = quote_identifier(table_name)
        info = self._conn.execute(f"PRAGMA table_info({quoted_name})").fetchall()
        return {row[1] for row in info}

    def list_tables(self) -> set[str]:
        """Return available table names."""
        rows = self._conn.execute("SHOW TABLES").fetchall()
        return {row[0] for row in rows}

    def read_table(self, name: str):
        """Read a table as an Ibis expression."""
        return self.ibis_conn.table(name)

    def replace_rows(self, table: str, rows: ibis.Table, *, by_keys: dict[str, object]) -> None:
        """Delete matching rows and insert replacements (UPSERT simulation)."""
        if not by_keys:
            msg = "replace_rows requires at least one key for deletion safety"
            raise ValueError(msg)

        quoted_table = quote_identifier(table)
        conditions = []
        params = []
        for col, val in by_keys.items():
            conditions.append(f"{quote_identifier(col)} = ?")
            params.append(val)

        where_clause = " AND ".join(conditions)
        sql = f"DELETE FROM {quoted_table} WHERE {where_clause}"

        self._conn.execute(sql, params)
        self.ibis_conn.insert(table, rows)


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
