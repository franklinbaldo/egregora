"""Centralized storage manager for DuckDB + Ibis operations.

Provides a unified interface for reading/writing tables with automatic
checkpointing. Refactored to reduce "Leaky Abstraction" and "Thread Locking" smells.
"""

from __future__ import annotations

import contextlib
import logging
import re
import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

import duckdb
import ibis
from ibis.expr.types import Table

from egregora.database import schemas
from egregora.database.ir_schema import quote_identifier
from egregora.database.sql import SQLManager

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

    Attributes:
        db_path: Path to DuckDB file (or None for in-memory)
        ibis_conn: Ibis backend connected to DuckDB (Preferred public interface)
        checkpoint_dir: Directory for parquet checkpoints

    """

    def __init__(
        self,
        db_path: Path | None = None,
        checkpoint_dir: Path | None = None,
    ) -> None:
        """Initialize storage manager."""
        self.db_path = db_path
        self.checkpoint_dir = checkpoint_dir or Path(".egregora/data")

        # Initialize DuckDB connection
        db_str = str(db_path) if db_path else ":memory:"
        self._conn = duckdb.connect(db_str)

        # Initialize Ibis backend
        self.ibis_conn = ibis.duckdb.connect(database=db_str)

        # Initialize SQL template manager
        self.sql = SQLManager()

        # Cache for PRAGMA table metadata
        self._table_info_cache: dict[str, set[str]] = {}

        logger.info(
            "DuckDBStorageManager initialized (db=%s, checkpoints=%s)",
            "memory" if db_path is None else db_path,
            self.checkpoint_dir,
        )
        self._lock = threading.Lock()

    @classmethod
    def from_connection(cls, conn: duckdb.DuckDBPyConnection, checkpoint_dir: Path | None = None) -> Self:
        """Create storage manager from an existing DuckDB connection."""
        instance = cls.__new__(cls)
        instance.db_path = None  # Unknown for external connections
        instance.checkpoint_dir = checkpoint_dir or Path(".egregora/data")
        instance._conn = conn
        db_list = conn.execute("PRAGMA database_list").fetchall()
        db_path = db_list[0][2] if db_list else None
        db_str = db_path or ":memory:"
        instance.ibis_conn = ibis.duckdb.connect(database=db_str)
        instance.sql = SQLManager()
        instance._table_info_cache = {}
        instance._lock = threading.Lock()
        logger.debug("DuckDBStorageManager created from existing connection")
        return instance

    def _is_invalidated_error(self, exc: duckdb.Error) -> bool:
        """Check if DuckDB raised a fatal invalidation error."""
        message = str(exc).lower()
        return "database has been invalidated" in message or "read-only but has made changes" in message

    def _reset_connection(self) -> None:
        """Recreate the DuckDB connection after a fatal error and clear caches."""
        db_str = str(self.db_path) if self.db_path else ":memory:"
        logger.warning("Resetting DuckDB connection after fatal error (db=%s)", db_str)

        # Ensure connection is fully closed before attempting any file operations
        try:
            self._conn.close()
        except Exception as close_exc:
            logger.error("Failed closing invalidated DuckDB connection: %s", close_exc)

        # Explicitly clear Ibis backend to release any internal handles
        if hasattr(self, "ibis_conn"):
            try:
                # Ibis backend doesn't always have a close method that closes the underlying connection
                # if it was created via connect(), but we try best effort.
                if hasattr(self.ibis_conn, "con") and hasattr(self.ibis_conn.con, "close"):
                    self.ibis_conn.con.close()
            except Exception:
                pass
            self.ibis_conn = None

        def _connect() -> None:
            self._conn = duckdb.connect(db_str)
            try:
                self.ibis_conn = ibis.duckdb.connect(database=db_str)
            except Exception as e:
                # If Ibis connection fails (e.g. race condition), we might still have a valid raw connection.
                # However, the manager is broken without Ibis.
                logger.error("Failed to reconnect Ibis backend: %s", e)
                raise

        try:
            _connect()
        except duckdb.Error as exc:
            if self._is_invalidated_error(exc) and self.db_path:
                logger.warning("Recreating DuckDB database file after fatal invalidation: %s", db_str)
                try:
                    Path(db_str).unlink(missing_ok=True)
                except Exception as unlink_exc:
                    logger.error("Failed to remove invalidated DuckDB file %s: %s", db_str, unlink_exc)

                # Final attempt to connect
                _connect()
            else:
                raise

        self.sql = SQLManager()
        self._table_info_cache.clear()

    @contextlib.contextmanager
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Yield the managed DuckDB connection.

        Supported escape hatch for direct access when needed.
        """
        yield self._conn

    def execute_query(self, sql: str, params: list | None = None) -> list:
        """Execute a raw SQL query and return all results."""
        params = params or []
        # TODO: Add validation or SQL construction via helper to reduce injection risk?
        # Current usage relies on params for values, but table names must be quoted by caller.
        return self._conn.execute(sql, params).fetchall()

    def _execute_sql(self, sql: str, params: Sequence | None = None) -> None:
        """Internal: Execute a raw SQL statement without returning results."""
        self._conn.execute(sql, params or [])

    def execute_sql(self, sql: str, params: Sequence | None = None) -> None:
        """Execute a raw SQL statement without returning results (Public wrapper).

        Prefer Ibis or specific helpers over this.
        """
        self._execute_sql(sql, params)

    def execute_query_single(self, sql: str, params: list | None = None) -> tuple | None:
        """Execute a raw SQL query and return a single result row."""
        params = params or []
        return self._conn.execute(sql, params).fetchone()

    def replace_rows(
        self,
        table: str,
        rows: Table,
        *,
        where_clause: str,
        params: Sequence | None = None,
    ) -> None:
        """Delete matching rows and insert replacements."""
        quoted_table = quote_identifier(table)
        self._execute_sql(f"DELETE FROM {quoted_table} WHERE {where_clause}", params)
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
                except Exception:
                    pass
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
            dataframe = table.execute()
            self._conn.register(name, dataframe)
            logger.info("Table '%s' written without checkpoint (%s)", name, mode)
        else:
            msg = "Append mode requires checkpoint=True"
            raise ValueError(msg)

    def persist_atomic(self, table: Table, name: str, schema: ibis.Schema) -> None:
        """Persist an Ibis table to a DuckDB table atomically using a transaction."""
        if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", name):
            msg = "target_table must be a valid DuckDB identifier"
            raise ValueError(msg)

        target_schema = schema
        schemas.create_table_if_not_exists(self._conn, name, target_schema)

        temp_view = f"_egregora_persist_{uuid.uuid4().hex}"
        self._conn.create_view(temp_view, table.to_pyarrow(), overwrite=True)

        try:
            sql = self.sql.render(
                "ddl/atomic_persist.sql.jinja",
                target_table=name,
                columns=target_schema.names,
                source_view=temp_view,
            )
            self._conn.execute(sql)
        finally:
            with contextlib.suppress(Exception):
                self._conn.unregister(temp_view)

    def get_table_columns(self, table_name: str, *, refresh: bool = False) -> set[str]:
        """Return cached column names for ``table_name``."""
        cache_key = table_name.lower()
        if refresh or cache_key not in self._table_info_cache:
            quote_identifier(table_name)

            try:
                rows = self._conn.execute(
                    f"PRAGMA table_info('{table_name}')",
                ).fetchall()
            except duckdb.Error:
                rows: list[tuple[str, ...]] = []

            self._table_info_cache[cache_key] = {row[1] for row in rows}

        return self._table_info_cache[cache_key]

    def ensure_sequence(self, name: str, *, start: int = 1) -> None:
        """Create a sequence if it does not exist."""
        quoted_name = quote_identifier(name)
        self._conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {quoted_name} START {int(start)}")

    def get_sequence_state(self, name: str) -> SequenceState | None:
        """Return metadata describing the current state of ``name``."""
        row = self._conn.execute(
            """
            SELECT start_value, increment_by, last_value
            FROM duckdb_sequences()
            WHERE schema_name = current_schema() AND sequence_name = ?
            LIMIT 1
            """,
            [name],
        ).fetchone()
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
        column_default = self._conn.execute(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE lower(table_name) = lower(?) AND lower(column_name) = lower(?)
            LIMIT 1
            """,
            [table, column],
        ).fetchone()
        if not column_default or column_default[0] != desired_default:
            quoted_table = quote_identifier(table)
            quoted_column = quote_identifier(column)
            self._conn.execute(
                f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_column} SET DEFAULT {desired_default}"
            )

    def sync_sequence_with_table(self, sequence_name: str, *, table: str, column: str) -> None:
        """Advance ``sequence_name`` so it is ahead of ``table.column``."""
        if not self.table_exists(table):
            return

        quoted_table = quote_identifier(table)
        quoted_column = quote_identifier(column)
        max_row = self._conn.execute(f"SELECT MAX({quoted_column}) FROM {quoted_table}").fetchone()
        if not max_row or max_row[0] is None:
            return

        max_value = int(max_row[0])
        state = self.get_sequence_state(sequence_name)
        if state is None:
            msg = f"Sequence '{sequence_name}' not found"
            raise RuntimeError(msg)

        current_next = state.next_value
        desired_next = max(max_value + 1, current_next)
        steps_needed = desired_next - current_next
        if steps_needed > 0:
            self.next_sequence_values(sequence_name, count=steps_needed)

    def next_sequence_value(self, sequence_name: str) -> int:
        """Return the next value from ``sequence_name``."""
        values = self.next_sequence_values(sequence_name, count=1)
        return values[0]

    def next_sequence_values(self, sequence_name: str, *, count: int = 1) -> list[int]:
        """Return ``count`` sequential values from ``sequence_name``."""
        if count <= 0:
            msg = "count must be positive"
            raise ValueError(msg)

        # Thread locking is necessary here because DuckDB connections are not thread-safe
        # when accessed concurrently, and nextval() modifies state.
        with self._lock:
            try:
                cursor = self._conn.execute("SELECT nextval(?) FROM range(?)", [sequence_name, count])
                values = [int(row[0]) for row in cursor.fetchall()]
            except duckdb.Error as exc:
                if not self._is_invalidated_error(exc):
                    raise

                self._reset_connection()
                cursor = self._conn.execute("SELECT nextval(?) FROM range(?)", [sequence_name, count])
                values = [int(row[0]) for row in cursor.fetchall()]

        if not values:
            state = self.get_sequence_state(sequence_name)
            if state is None:
                logger.warning("Sequence '%s' not found, creating it", sequence_name)
                self.ensure_sequence(sequence_name)
                cursor = self._conn.execute("SELECT nextval(?) FROM range(?)", [sequence_name, count])
                values = [int(row[0]) for row in cursor.fetchall()]
            else:
                msg = f"Sequence '{sequence_name}' exists but nextval query returned no results"
                raise RuntimeError(msg)

        return values

    def table_exists(self, name: str) -> bool:
        """Check if table exists in database."""
        tables = self._conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = ?
        """,
            [name],
        ).fetchall()
        return len(tables) > 0

    def list_tables(self) -> list[str]:
        """List all tables in database."""
        tables = self._conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
        """
        ).fetchall()
        return [t[0] for t in tables]

    def drop_table(self, name: str, *, checkpoint_too: bool = False) -> None:
        """Drop table from database."""
        quoted_name = quote_identifier(name)
        with contextlib.suppress(Exception):
            self._conn.execute(f"DROP VIEW IF EXISTS {quoted_name}")
        with contextlib.suppress(Exception):
            self._conn.execute(f"DROP TABLE IF EXISTS {quoted_name}")
        logger.info("Dropped table/view: %s", name)

        if checkpoint_too:
            parquet_path = self.checkpoint_dir / f"{name}.parquet"
            if parquet_path.exists():
                parquet_path.unlink()
                logger.info("Deleted checkpoint: %s", parquet_path)

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()
        logger.info("DuckDBStorageManager closed")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type: object, _exc_val: object, _exc_tb: object) -> None:
        self.close()

    def drop_index(self, name: str) -> None:
        quoted = quote_identifier(name)
        self._conn.execute(f"DROP INDEX IF EXISTS {quoted}")

    def row_count(self, table_name: str) -> int:
        if not self.table_exists(table_name):
            return 0
        quoted = quote_identifier(table_name)
        row = self._conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()
        return int(row[0]) if row and row[0] is not None else 0


def temp_storage() -> DuckDBStorageManager:
    """Create temporary in-memory storage manager."""
    return DuckDBStorageManager(db_path=None, checkpoint_dir=Path("/tmp/.egregora-temp"))  # noqa: S108


@contextlib.contextmanager
def duckdb_backend() -> ibis.BaseBackend:
    """Context manager for temporary DuckDB backend."""
    connection = duckdb.connect(":memory:")
    backend = ibis.duckdb.from_connection(connection)
    old_backend = getattr(ibis.options, "default_backend", None)
    try:
        ibis.options.default_backend = backend
        logger.debug("DuckDB backend initialized")
        yield backend
    finally:
        ibis.options.default_backend = old_backend
        connection.close()
        logger.debug("DuckDB backend closed")


__all__ = [
    "DuckDBStorageManager",
    "duckdb_backend",
    "quote_identifier",
    "temp_storage",
]
