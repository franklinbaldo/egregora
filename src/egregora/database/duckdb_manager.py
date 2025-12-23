"""Centralized storage manager for DuckDB + Ibis operations.

Provides a unified interface for reading/writing tables with automatic
checkpointing.
"""

from __future__ import annotations

import contextlib
import logging
import re
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

import duckdb
import ibis

from egregora.database import schemas
from egregora.database.ir_schema import quote_identifier
from egregora.database.sql import SQLManager

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ibis.expr.types import Table

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SequenceState:
    """Metadata describing the current state of a DuckDB sequence."""

    sequence_name: str
    start_value: int
    increment_by: int
    last_value: int | None

    @property
    def next_value(self) -> int:
        """Return the value that will be produced by the next ``nextval`` call."""
        if self.last_value is None:
            return self.start_value
        return self.last_value + self.increment_by


class DuckDBStorageManager:
    """Centralized DuckDB connection + Ibis helpers.

    Manages database connections on a per-thread basis to ensure thread safety.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        checkpoint_dir: Path | None = None,
    ) -> None:
        """Initialize storage manager."""
        self.db_path = db_path
        self.checkpoint_dir = checkpoint_dir or Path(".egregora/data")
        self._thread_local = threading.local()
        self.sql = SQLManager()
        self._table_info_cache: dict[str, set[str]] = {}
        self._file_lock = threading.RLock()  # For file-level operations like checkpoints

        logger.info(
            "DuckDBStorageManager initialized (db=%s, checkpoints=%s)",
            "memory" if db_path is None else db_path,
            self.checkpoint_dir,
        )

    def _get_thread_connections(self) -> tuple[duckdb.DuckDBPyConnection, ibis.BaseBackend]:
        """Get or create a connection and Ibis backend for the current thread."""
        conn = getattr(self._thread_local, "conn", None)
        is_closed = getattr(conn, "is_closed", True)

        if conn is None or is_closed:
            db_str = str(self.db_path) if self.db_path else ":memory:"
            ibis_conn = ibis.duckdb.connect(database=db_str, read_only=False)
            conn = ibis_conn.con
            self._thread_local.conn = conn
            self._thread_local.ibis_conn = ibis_conn

        return self._thread_local.conn, self._thread_local.ibis_conn

    @property
    def _conn(self) -> duckdb.DuckDBPyConnection:
        """Property to access the thread-local connection."""
        conn, _ = self._get_thread_connections()
        return conn

    @property
    def ibis_conn(self) -> ibis.BaseBackend:
        """Property to access the thread-local Ibis backend."""
        _, ibis_conn = self._get_thread_connections()
        return ibis_conn

    @classmethod
    def from_connection(cls, conn: duckdb.DuckDBPyConnection, checkpoint_dir: Path | None = None) -> Self:
        """Create storage manager from an existing DuckDB connection."""
        db_path = None
        try:
            db_list = conn.execute("PRAGMA database_list").fetchall()
            db_file = db_list[0][2] if db_list and db_list[0][2] else None
            db_path = Path(db_file) if db_file else None
        except duckdb.Error:
            pass

        instance = cls(db_path=db_path, checkpoint_dir=checkpoint_dir)
        db_str = str(db_path) if db_path else ":memory:"
        instance._thread_local.conn = conn
        instance._thread_local.ibis_conn = ibis.duckdb.connect(database=db_str)
        return instance

    @classmethod
    def from_ibis_backend(cls, backend: ibis.BaseBackend, checkpoint_dir: Path | None = None) -> Self:
        """Create storage manager from an existing Ibis backend."""
        db_path = None
        if hasattr(backend, "con"):
            try:
                db_list = backend.con.execute("PRAGMA database_list").fetchall()
                db_file = db_list[0][2] if db_list and db_list[0][2] else None
                db_path = Path(db_file) if db_file else None
            except duckdb.Error:
                pass

        instance = cls(db_path=db_path, checkpoint_dir=checkpoint_dir)

        if hasattr(backend, "con"):
            instance._thread_local.conn = backend.con
            instance._thread_local.ibis_conn = backend
        else:
            msg = "Provided backend does not expose a raw 'con' attribute"
            raise ValueError(msg)

        return instance

    def _is_invalidated_error(self, exc: duckdb.Error) -> bool:
        """Check if DuckDB raised a fatal invalidation error."""
        message = str(exc).lower()
        return "database has been invalidated" in message or "read-only but has made changes" in message

    def _reset_connection(self) -> None:
        """Recreate the DuckDB connection for the current thread."""
        logger.warning("Resetting DuckDB connection for thread %s", threading.get_ident())
        if hasattr(self._thread_local, "conn"):
            try:
                self._thread_local.conn.close()
            except Exception:
                logger.exception("Failed closing invalidated DuckDB connection")

        if hasattr(self._thread_local, "conn"):
            del self._thread_local.conn
        if hasattr(self._thread_local, "ibis_conn"):
            del self._thread_local.ibis_conn

        self.sql = SQLManager()
        self._table_info_cache.clear()

    @contextlib.contextmanager
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Yield the managed DuckDB connection."""
        yield self._conn

    def execute_query(self, sql: str, params: list | None = None) -> list:
        """Execute a raw SQL query and return all results."""
        params = params or []
        return self._conn.execute(sql, params).fetchall()

    def execute(self, sql: str, params: Sequence | None = None) -> duckdb.DuckDBPyRelation:
        """Execute a raw SQL statement via the managed connection."""
        return self._conn.execute(sql, params or [])

    def execute_sql(self, sql: str, params: Sequence | None = None) -> None:
        """Execute a raw SQL statement without returning results."""
        self._conn.execute(sql, params or [])

    def execute_query_single(self, sql: str, params: list | None = None) -> tuple | None:
        """Execute a raw SQL query and return a single result row."""
        params = params or []
        return self._conn.execute(sql, params).fetchone()

    def replace_rows(
        self,
        table: str,
        rows: Table,
        *,
        by_keys: dict[str, Any],
    ) -> None:
        """Delete matching rows and insert replacements (UPSERT simulation)."""
        if not by_keys:
            raise ValueError("replace_rows requires at least one key for deletion safety")

        quoted_table = quote_identifier(table)

        conditions = []
        params = []
        for col, val in by_keys.items():
            conditions.append(f"{quote_identifier(col)} = ?")
            params.append(val)

        where_clause = " AND ".join(conditions)
        sql = f"DELETE FROM {quoted_table} WHERE {where_clause}"

        self.execute_sql(sql, params)
        self.ibis_conn.insert(table, rows)

    def read_table(self, name: str) -> Table:
        """Read table as Ibis expression."""
        try:
            return self.ibis_conn.table(name)
        except Exception as e:
            if self._is_invalidated_error(e):
                self._reset_connection()
                try:
                    return self.ibis_conn.table(name)
                except duckdb.Error as retry_exc:
                    logger.debug("Retry after connection reset failed: %s", retry_exc)
            msg = f"Table '{name}' not found in database"
            logger.exception(msg)
            raise ValueError(msg) from e

    def write_table(
        self,
        table: Table,
        name: str,
        mode: Literal["replace", "append"] = "replace",
        *,
        checkpoint: bool = True,
    ) -> None:
        """Write Ibis table to DuckDB."""
        if checkpoint:
            with self._file_lock:
                parquet_path = self.checkpoint_dir / f"{name}.parquet"
                parquet_path.parent.mkdir(parents=True, exist_ok=True)

                logger.debug("Writing checkpoint: %s", parquet_path)
                table.to_parquet(str(parquet_path))

                sql = self.sql.render(
                    "dml/load_parquet.sql.jinja",
                    table_name=name,
                    mode=mode,
                )
                params = [str(parquet_path)] if mode == "replace" else [str(parquet_path), str(parquet_path)]
                self._conn.execute(sql, params)
                logger.info("Table '%s' written with checkpoint (%s)", name, mode)

        elif mode == "replace":
            with self._file_lock:
                dataframe = table.execute()
                self._conn.register(name, dataframe)
                logger.info("Table '%s' written without checkpoint (%s)", name, mode)
        else:
            msg = "Append mode requires checkpoint=True"
            raise ValueError(msg)

    def list_tables(self) -> list[str]:
        """List all tables in database."""
        tables = self.execute_query(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        )
        return [t[0] for t in tables]

    def table_exists(self, name: str) -> bool:
        """Check if table exists in database."""
        tables = self.execute_query(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            [name],
        )
        return len(tables) > 0

    def ensure_sequence(self, name: str, *, start: int = 1) -> None:
        """Create a sequence if it does not exist."""
        self.execute_sql(f"CREATE SEQUENCE IF NOT EXISTS {quote_identifier(name)} START {int(start)}")
        self._conn.commit()

    def get_sequence_state(self, name: str) -> SequenceState | None:
        """Return metadata describing the current state of ``name``."""
        row = self.execute_query_single(
            "SELECT start_value, increment_by, last_value FROM duckdb_sequences() WHERE sequence_name = ?",
            [name],
        )
        if row is None:
            return None
        start_value, increment_by, last_value = row
        return SequenceState(
            sequence_name=name,
            start_value=int(start_value),
            increment_by=int(increment_by),
            last_value=None if last_value is None else int(last_value),
        )

    def ensure_sequence_default(self, table: str, column: str, sequence_name: str) -> None:
        """Ensure ``column`` uses ``sequence_name`` as its default value."""
        desired_default = f"nextval('{sequence_name}')"
        row = self.execute_query_single(
            "SELECT column_default FROM information_schema.columns WHERE lower(table_name) = lower(?) AND lower(column_name) = lower(?)",
            [table, column],
        )
        if not row or row[0] != desired_default:
            quoted_table = quote_identifier(table)
            quoted_column = quote_identifier(column)
            self.execute_sql(f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_column} SET DEFAULT {desired_default}")
            self._conn.commit()

    def sync_sequence_with_table(self, sequence_name: str, *, table: str, column: str) -> None:
        """Advance ``sequence_name`` so it is ahead of ``table.column``."""
        if not self.table_exists(table):
            return

        quoted_table = quote_identifier(table)
        quoted_column = quote_identifier(column)
        max_row = self.execute_query_single(f"SELECT MAX({quoted_column}) FROM {quoted_table}")
        if not max_row or max_row[0] is None:
            return

        max_value = int(max_row[0])
        state = self.get_sequence_state(sequence_name)
        if state is None:
            raise RuntimeError(f"Sequence '{sequence_name}' not found")

        current_next = state.next_value
        desired_next = max(max_value + 1, current_next)
        steps_needed = desired_next - current_next
        if steps_needed > 0:
            self.next_sequence_values(sequence_name, count=steps_needed)

    def next_sequence_value(self, sequence_name: str) -> int:
        """Return the next value from ``sequence_name``."""
        row = self.execute_query_single(
            "SELECT nextval('{}')".format(sequence_name.replace("'", "''"))
        )
        if row is None:
            msg = f"Failed to fetch next value for sequence '{sequence_name}'"
            raise RuntimeError(msg)
        return int(row[0])

    def next_sequence_values(self, sequence_name: str, *, count: int = 1) -> list[int]:
        """Return ``count`` sequential values from ``sequence_name``."""
        if count <= 0:
            raise ValueError("count must be positive")

        def _fetch_values() -> list[int]:
            results: list[int] = []
            for _ in range(count):
                row = self.execute_query_single(
                    "SELECT nextval('{}')".format(sequence_name.replace("'", "''"))
                )
                if row is None:
                    raise RuntimeError(f"Failed to fetch next value for sequence '{sequence_name}'")
                results.append(int(row[0]))
            return results

        try:
            return _fetch_values()
        except duckdb.Error as exc:
            if not self._is_invalidated_error(exc):
                raise
            self._reset_connection()
            self.ensure_sequence(sequence_name)
            return _fetch_values()

    def close(self) -> None:
        """Close database connection for the current thread."""
        if hasattr(self._thread_local, "conn"):
            self._thread_local.conn.close()
            logger.info("DuckDB connection closed for thread %s", threading.get_ident())

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type: object, _exc_val: object, _exc_tb: object) -> None:
        self.close()

def temp_storage() -> DuckDBStorageManager:
    """Create temporary in-memory storage manager."""
    return DuckDBStorageManager(db_path=None)


@contextlib.contextmanager
def duckdb_backend() -> ibis.BaseBackend:
    """Context manager for temporary DuckDB backend."""
    backend = ibis.duckdb.connect(":memory:")
    old_backend = getattr(ibis.options, "default_backend", None)
    try:
        ibis.options.default_backend = backend
        yield backend
    finally:
        ibis.options.default_backend = old_backend
        if hasattr(backend, "disconnect"):
            backend.disconnect()

__all__ = [
    "DuckDBStorageManager",
    "duckdb_backend",
    "quote_identifier",
    "temp_storage",
]
