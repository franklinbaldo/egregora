"""Database utility functions."""

import contextlib
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import duckdb
from ibis.common.exceptions import IbisError
from ibis.expr.types import Table

from egregora.database.streaming import ensure_deterministic_order, stream_ibis


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
        """List all tables in the database."""
        return {row[0] for row in self._conn.execute("SHOW TABLES").fetchall()}

    def read_table(self, table_name: str) -> duckdb.DuckDBPyRelation:
        """Read a table from the database."""
        return self._conn.table(table_name)


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


def frame_to_records(frame: Any) -> list[dict[str, Any]]:
    """Convert backend frames into dict records consistently."""
    if hasattr(frame, "to_dict"):
        return [dict(row) for row in frame.to_dict("records")]
    if hasattr(frame, "to_pylist"):
        try:
            return [dict(row) for row in frame.to_pylist()]
        except (
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:  # pragma: no cover - defensive
            msg = f"Failed to convert frame to records. Original error: {exc}"
            raise RuntimeError(msg) from exc
    return [dict(row) for row in frame]


def iter_table_batches(table: Table, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
    """Stream table rows as batches of dictionaries without loading entire table into memory."""
    try:
        backend = table._find_backend()
    except (AttributeError, IbisError):  # pragma: no cover - fallback path
        backend = None

    if backend is not None and hasattr(backend, "con"):
        ordered_table = ensure_deterministic_order(table)
        yield from stream_ibis(ordered_table, backend, batch_size=batch_size)
        return

    if "ts" in table.columns:
        table = table.order_by("ts")

    results_df = table.execute()
    records = frame_to_records(results_df)
    for start in range(0, len(records), batch_size):
        yield records[start : start + batch_size]
