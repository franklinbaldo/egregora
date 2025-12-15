"""Centralized storage manager for DuckDB + Ibis operations.

Provides a unified interface for reading/writing tables with automatic
checkpointing.

This module implements Priority C.2 from the Architecture Roadmap:
centralized DuckDB access to eliminate raw SQL and provide consistent
checkpoint management across pipeline stages.

Callers should treat :class:`DuckDBStorageManager` as the single entry point
for metadata queries and bookkeeping. Avoid holding on to the raw
``duckdb.Connection`` object; instead use helper methods like
:meth:`get_table_columns`, :meth:`fetch_latest_runs`, or the
:meth:`connection` context manager when absolutely necessary.

Usage:
    from egregora.database.duckdb_manager import DuckDBStorageManager

    # Create storage manager
    storage = DuckDBStorageManager(db_path=Path("pipeline.duckdb"))

    # Read table as Ibis
    table = storage.read_table("conversations")

    # Write table with checkpoint
    storage.write_table(table, "enriched_conversations")

    # Execute a named view
    from egregora.database.views import COMMON_VIEWS

    chunks_builder = COMMON_VIEWS["chunks"]
    result = storage.execute_view("chunks", chunks_builder, "conversations")
"""

from __future__ import annotations

import contextlib
import logging
import re
import tempfile
import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Self

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

    Manages database connections, table I/O, and automatic checkpointing
    for pipeline stages. View transformations are provided as callables
    (see :mod:`egregora.database.views`).

    Attributes:
        db_path: Path to DuckDB file (or None for in-memory)
        _conn: Raw DuckDB connection (private - prefer helpers)
        ibis_conn: Ibis backend connected to DuckDB
        checkpoint_dir: Directory for parquet checkpoints

    Example:
        >>> storage = DuckDBStorageManager(db_path=Path("pipeline.duckdb"))
        >>> table = storage.read_table("conversations")
        >>> enriched = table.mutate(score=table.rating * 2)
        >>> storage.write_table(enriched, "conversations_enriched")

    """

    def __init__(
        self,
        db_path: Path | None = None,
        checkpoint_dir: Path | None = None,
    ) -> None:
        """Initialize storage manager.

        Args:
            db_path: Path to DuckDB file (None = in-memory database)
            checkpoint_dir: Directory for parquet checkpoints
                          (defaults to .egregora/data/)

        """
        self.db_path = db_path
        self.checkpoint_dir = checkpoint_dir or Path(".egregora/data")

        # Initialize Ibis backend first (it manages the DuckDB connection)
        db_str = str(db_path) if db_path else ":memory:"
        self.ibis_conn = ibis.duckdb.connect(database=db_str, read_only=False)

        # Use the underlying DuckDB connection from Ibis to ensure we share the same connection
        # This prevents "read-only transaction" errors caused by multiple connections to the same file
        self._conn = self.ibis_conn.con

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
        """Create storage manager from an existing DuckDB connection.

        This properly initializes both the raw connection and Ibis backend
        from an existing connection, avoiding the mutation pattern that
        breaks ibis_conn synchronization.

        Args:
            conn: Existing DuckDB connection
            checkpoint_dir: Directory for parquet checkpoints

        Returns:
            Storage manager instance with properly initialized backends

        """
        instance = cls.__new__(cls)
        instance.db_path = None  # Unknown for external connections
        instance.checkpoint_dir = checkpoint_dir or Path(".egregora/data")
        instance._conn = conn
        db_list = conn.execute("PRAGMA database_list").fetchall()
        # PRAGMA database_list returns rows as (oid, name, file)
        db_path = db_list[0][2] if db_list else None
        db_str = db_path or ":memory:"
        # Note: ibis.connect(conn) is not supported in current version, so we create a separate connection.
        # This might cause concurrency issues if not handled carefully.
        # Ideally we would use the same connection, but for now we accept the limitation for from_connection.
        # CRITICAL: Must use read_only=False to avoid "read-only transaction made changes" errors
        instance.ibis_conn = ibis.duckdb.connect(database=db_str, read_only=False)
        instance.sql = SQLManager()
        instance._table_info_cache = {}
        instance._lock = threading.Lock()
        logger.debug("DuckDBStorageManager created from existing connection")
        return instance

    @classmethod
    def from_ibis_backend(cls, backend: ibis.BaseBackend, checkpoint_dir: Path | None = None) -> Self:
        """Create storage manager from an existing Ibis backend.

        This ensures the storage manager shares the exact same connection
        as the provided backend, preventing multi-connection conflicts.

        Args:
            backend: Existing Ibis backend (must be DuckDB)
            checkpoint_dir: Directory for parquet checkpoints

        Returns:
            Storage manager instance sharing the backend's connection

        """
        instance = cls.__new__(cls)
        instance.checkpoint_dir = checkpoint_dir or Path(".egregora/data")

        instance.ibis_conn = backend
        # Share the raw connection from the backend
        if hasattr(backend, "con"):
            instance._conn = backend.con
        else:
            msg = "Provided backend does not expose a raw 'con' attribute (expected DuckDB backend)"
            raise ValueError(msg)

        # Extract db_path from connection so _reset_connection works correctly
        # PRAGMA database_list returns rows as (oid, name, file)
        try:
            db_list = instance._conn.execute("PRAGMA database_list").fetchall()
            db_file = db_list[0][2] if db_list and db_list[0][2] else None
            instance.db_path = Path(db_file) if db_file else None
        except Exception:
            instance.db_path = None
            logger.debug("Could not determine db_path from backend connection")

        instance.sql = SQLManager()
        instance._table_info_cache = {}
        instance._lock = threading.Lock()
        logger.debug("DuckDBStorageManager created from existing Ibis backend (db_path=%s)", instance.db_path)
        return instance

    def _is_invalidated_error(self, exc: duckdb.Error) -> bool:
        """Check if DuckDB raised a fatal invalidation error."""
        message = str(exc).lower()
        return "database has been invalidated" in message or "read-only but has made changes" in message

    def _reset_connection(self) -> None:
        """Recreate the DuckDB connection after a fatal error and clear caches."""
        db_str = str(self.db_path) if self.db_path else ":memory:"
        logger.warning("Resetting DuckDB connection after fatal error (db=%s)", db_str)
        try:
            self._conn.close()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed closing invalidated DuckDB connection")

        def _connect() -> None:
            # Re-initialize via Ibis to maintain shared connection
            # Explicitly request read_write access
            self.ibis_conn = ibis.duckdb.connect(database=db_str, read_only=False)
            self._conn = self.ibis_conn.con

        try:
            _connect()
        except Exception as exc:
            # Check for specific invalidation error that requires file removal
            if isinstance(exc, duckdb.Error) and self._is_invalidated_error(exc) and self.db_path:
                logger.warning("Recreating DuckDB database file after fatal invalidation: %s", db_str)
                try:
                    Path(db_str).unlink(missing_ok=True)
                    _connect()
                    return
                except Exception:
                    logger.exception("Failed to recover via file deletion")

            # Fallback to memory if file open/recovery fails
            logger.warning("Failed to reconnect to %s, falling back to memory. Error: %s", db_str, exc)
            db_str = ":memory:"
            try:
                _connect()
            except Exception:
                msg = "Critical failure: Could not connect to in-memory database after reset"
                logger.critical(msg)
                raise RuntimeError(msg) from exc

        self.db_path = Path(db_str) if db_str != ":memory:" else None
        logger.info("DuckDB connection reset successfully (db=%s)", db_str)

        self.sql = SQLManager()
        self._table_info_cache.clear()

    @contextlib.contextmanager
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Yield the managed DuckDB connection.

        This is the supported escape hatch for code that still needs direct
        access to DuckDB. Callers should prefer dedicated helper methods when
        available and avoid caching the returned handle.
        """
        yield self._conn

    def execute_query(self, sql: str, params: list | None = None) -> list:
        """Execute a raw SQL query and return all results.

        This is the preferred way to run raw SQL when Ibis is insufficient.
        It replaces direct access to ``self.conn``.

        Args:
            sql: SQL query string
            params: Optional list of parameters for prepared statement

        Returns:
            List of result tuples

        """
        params = params or []
        return self._conn.execute(sql, params).fetchall()

    def execute_sql(self, sql: str, params: Sequence | None = None) -> None:
        """Execute a raw SQL statement without returning results."""
        self._conn.execute(sql, params or [])

    def execute_query_single(self, sql: str, params: list | None = None) -> tuple | None:
        """Execute a raw SQL query and return a single result row.

        Args:
            sql: SQL query string
            params: Optional list of parameters

        Returns:
            Single result tuple or None

        """
        params = params or []
        return self._conn.execute(sql, params).fetchone()

    def replace_rows(
        self,
        table: str,
        rows: Table,
        *,
        by_keys: dict[str, Any],
    ) -> None:
        """Delete matching rows and insert replacements (UPSERT simulation).

        Simulates UPSERT by deleting rows matching the provided key-value pairs
        and then inserting the new rows. This prevents SQL injection by rigidly
        structuring the DELETE clause.

        Args:
            table: Target table name
            rows: Ibis table expression containing new rows
            by_keys: Dictionary of column_name -> value to match for deletion

        """
        if not by_keys:
            msg = "replace_rows requires at least one key for deletion safety"
            raise ValueError(msg)

        quoted_table = quote_identifier(table)

        # Build parameterized WHERE clause
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
        """Read table as Ibis expression.

        Args:
            name: Table name in DuckDB

        Returns:
            Ibis table expression

        Raises:
            ValueError: If table doesn't exist

        Example:
            >>> table = storage.read_table("conversations")
            >>> df = table.execute()

        """
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
        """Write Ibis table to DuckDB.

        Args:
            table: Ibis table expression to write
            name: Destination table name
            mode: Write mode ("replace" or "append")
            checkpoint: If True, save parquet checkpoint to disk

        Example:
            >>> enriched = table.mutate(score=...)
            >>> storage.write_table(enriched, "conversations_enriched")

        """
        if checkpoint:
            with self._lock:
                # Write checkpoint to parquet
                parquet_path = self.checkpoint_dir / f"{name}.parquet"
                parquet_path.parent.mkdir(parents=True, exist_ok=True)

                logger.debug("Writing checkpoint: %s", parquet_path)
                table.to_parquet(str(parquet_path))

                # Load into DuckDB from parquet
                sql = self.sql.render(
                    "dml/load_parquet.sql.jinja",
                    table_name=name,
                    mode=mode,
                )
                params = [str(parquet_path)] if mode == "replace" else [str(parquet_path), str(parquet_path)]
                self._conn.execute(sql, params)
                logger.info("Table '%s' written with checkpoint (%s)", name, mode)

        # Direct write without checkpoint (faster but no persistence)
        elif mode == "replace":
            with self._lock:
                # Use Ibis to_sql for direct write
                # Note: This requires executing the table first
                dataframe = table.execute()
                self._conn.register(name, dataframe)
                logger.info("Table '%s' written without checkpoint (%s)", name, mode)
        else:
            msg = "Append mode requires checkpoint=True"
            raise ValueError(msg)

    def persist_atomic(self, table: Table, name: str, schema: ibis.Schema) -> None:
        """Persist an Ibis table to a DuckDB table atomically using a transaction.

        This preserves existing table properties (like indexes) by performing a
        DELETE + INSERT transaction instead of dropping and recreating the table.

        Args:
            table: Ibis table to persist
            name: Target table name (must be valid SQL identifier)
            schema: Table schema to use for validation and column selection

        """
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
        """Return cached column names for ``table_name``.

        This utility wraps DuckDB's ``PRAGMA table_info`` with identifier
        validation and caching so that callers no longer need to run SQL.
        Missing tables simply return an empty set.
        """
        cache_key = table_name.lower()
        if refresh or cache_key not in self._table_info_cache:
            # Validate identifier (raises ValueError on invalid characters)
            quote_identifier(table_name)

            try:
                rows = self._conn.execute(
                    f"PRAGMA table_info('{table_name}')",
                ).fetchall()
            except duckdb.Error:
                rows: list[tuple[str, ...]] = []

            # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
            # We want row[1] which is the column name, not row[0] which is the cid (int)
            self._table_info_cache[cache_key] = {row[1] for row in rows}

        return self._table_info_cache[cache_key]

    # ==================================================================
    # Sequence helpers
    # ==================================================================

    def ensure_sequence(self, name: str, *, start: int = 1) -> None:
        """Create a sequence if it does not exist."""
        quoted_name = quote_identifier(name)
        logger.debug("Creating sequence %s if not exists", name)
        self._conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {quoted_name} START {int(start)}")
        self._conn.commit()
        # Verify sequence was created
        state = self.get_sequence_state(name)
        if state is None:
            logger.error("Failed to create sequence %s - sequence not found after creation", name)
            msg = f"Sequence {name} was not created"
            raise RuntimeError(msg)
        logger.debug("Sequence %s verified (start=%d)", name, state.start_value)

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
            self._conn.commit()

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

        with self._lock:
            try:
                # Rollback any pending transaction, then start a fresh write transaction
                try:
                    self._conn.rollback()
                except duckdb.Error:
                    pass  # Rollback may fail if no transaction is active

                # Explicitly begin a write transaction before nextval() to avoid
                # "read-only transaction but has made changes" error
                self._conn.begin()
                cursor = self._conn.execute("SELECT nextval(?) FROM range(?)", [sequence_name, count])
                values = [int(row[0]) for row in cursor.fetchall()]
                self._conn.commit()
            except duckdb.Error as exc:
                if not self._is_invalidated_error(exc):
                    raise

                # DuckDB occasionally invalidates the connection after a fatal internal error.
                # Recreate the connection and retry once so the pipeline can continue.
                logger.warning("DuckDB connection invalidated, resetting: %s", exc)
                self._reset_connection()

                # After connection reset, ensure sequence exists (may have been lost)
                state = self.get_sequence_state(sequence_name)
                if state is None:
                    logger.warning(
                        "Sequence '%s' not found after connection reset, recreating", sequence_name
                    )
                    self.ensure_sequence(sequence_name)

                try:
                    self._conn.begin()
                    cursor = self._conn.execute("SELECT nextval(?) FROM range(?)", [sequence_name, count])
                    values = [int(row[0]) for row in cursor.fetchall()]
                    self._conn.commit()
                except duckdb.Error as retry_exc:
                    logger.exception("Retry after connection reset also failed: %s", retry_exc)
                    raise

        # Defensive check: if query returns empty, sequence might not exist
        if not values:
            # Check if sequence exists
            state = self.get_sequence_state(sequence_name)
            if state is None:
                # Sequence doesn't exist - create it
                logger.warning("Sequence '%s' not found, creating it", sequence_name)
                self.ensure_sequence(sequence_name)
                # Retry the query
                cursor = self._conn.execute("SELECT nextval(?) FROM range(?)", [sequence_name, count])
                values = [int(row[0]) for row in cursor.fetchall()]
            else:
                # Sequence exists but query returned empty - this is unexpected
                msg = f"Sequence '{sequence_name}' exists but nextval query returned no results"
                raise RuntimeError(msg)

        return values

    def table_exists(self, name: str) -> bool:
        """Check if table exists in database.

        Args:
            name: Table name

        Returns:
            True if table exists, False otherwise

        """
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
        """List all tables in database.

        Returns:
            Sorted list of table names

        """
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
        """Drop table from database.

        Args:
            name: Table name
            checkpoint_too: If True, also delete parquet checkpoint

        Example:
            >>> storage.drop_table("temp_results", checkpoint_too=True)

        """
        # Try dropping as view first (ibis.memtable creates views), then table
        # Use quoted identifier to prevent SQL injection
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
        """Close database connection.

        Call this when done with the storage manager to clean up resources.
        """
        self._conn.close()
        logger.info("DuckDBStorageManager closed")

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(self, _exc_type: object, _exc_val: object, _exc_tb: object) -> None:
        """Context manager exit - closes connection."""
        self.close()

    # ==================================================================
    # Vector backend helpers (Consolidated)
    # ==================================================================

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
    """Create temporary in-memory storage manager.

    Returns:
        DuckDBStorageManager with in-memory database

    Example:
        >>> with temp_storage() as storage:
        ...     storage.write_table(my_table, "temp")
        ...     result = storage.read_table("temp")

    """
    # Use standard temporary directory instead of hardcoded /tmp path
    temp_dir = Path(tempfile.gettempdir()) / ".egregora-temp"
    return DuckDBStorageManager(db_path=None, checkpoint_dir=temp_dir)


@contextlib.contextmanager
def duckdb_backend() -> ibis.BaseBackend:
    """Context manager for temporary DuckDB backend.

    MODERN (Phase 2.2): Moved from connection.py to storage.py for consolidation.

    Sets up an in-memory DuckDB database as the default Ibis backend,
    and properly cleans up connections on exit.

    Yields:
        Ibis backend connected to DuckDB

    Example:
        >>> with duckdb_backend():
        ...     table = ibis.read_csv("data.csv")
        ...     result = table.execute()

    """
    # In ibis 9.0+, use connect() with database path directly
    # We don't need to create a raw duckdb connection first
    backend = ibis.duckdb.connect(":memory:")
    old_backend = getattr(ibis.options, "default_backend", None)
    try:
        ibis.options.default_backend = backend
        logger.debug("DuckDB backend initialized")
        yield backend
    finally:
        ibis.options.default_backend = old_backend
        # Close backend to release resources
        if hasattr(backend, "disconnect"):
            backend.disconnect()
        logger.debug("DuckDB backend closed")


__all__ = [
    "DuckDBStorageManager",
    "duckdb_backend",
    "quote_identifier",
    "temp_storage",
]
