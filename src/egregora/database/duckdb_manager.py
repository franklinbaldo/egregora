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
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

import duckdb
import ibis
from ibis.expr.types import Table

from egregora.database import schemas
from egregora.database.ir_schema import IR_MESSAGE_SCHEMA

logger = logging.getLogger(__name__)


def quote_identifier(name: str) -> str:
    """Safely quote a SQL identifier to prevent injection.

    Args:
        name: Table/view/column name

    Returns:
        Quoted identifier safe for SQL

    Raises:
        ValueError: If name contains invalid characters

    Example:
        >>> quote_identifier("my_table")
        '"my_table"'
        >>> quote_identifier("users; DROP TABLE users")
        ValueError: Invalid identifier name

    """
    # Allow only alphanumeric, underscore, hyphen
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        msg = f"Invalid identifier name: {name!r}. Only alphanumeric, underscore, and hyphen allowed."
        raise ValueError(msg)

    # Quote with double quotes (DuckDB identifier quoting)
    return f'"{name}"'


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


def combine_with_enrichment_rows(
    messages_table: Table,
    new_rows: list[dict],
    schema: ibis.Schema | None = None,
) -> Table:
    """Combines a base messages table with new enrichment rows."""
    target_schema = schema or IR_MESSAGE_SCHEMA
    messages_table_filtered = messages_table.select(*target_schema.names)

    # Ensure timestamps are UTC
    if "ts" in messages_table_filtered.columns:
        messages_table_filtered = messages_table_filtered.mutate(
            ts=messages_table_filtered.ts.cast("timestamp('UTC')")
        )
    elif "timestamp" in messages_table_filtered.columns:
        messages_table_filtered = messages_table_filtered.mutate(
            timestamp=messages_table_filtered.timestamp.cast("timestamp('UTC', 9)")
        )

    messages_table_filtered = messages_table_filtered.cast(target_schema)

    if new_rows:
        normalized_rows = [{column: row.get(column) for column in target_schema.names} for row in new_rows]
        enrichment_table = ibis.memtable(normalized_rows).cast(target_schema)
        combined = messages_table_filtered.union(enrichment_table, distinct=False)

        sort_col = "ts" if "ts" in target_schema.names else "timestamp"
        combined = combined.order_by(sort_col)
    else:
        combined = messages_table_filtered

    return combined


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

        # Initialize DuckDB connection
        db_str = str(db_path) if db_path else ":memory:"
        self._conn = duckdb.connect(db_str)

        # Initialize vector extensions
        self._vss_function: str | None = None
        self._init_vector_extensions()

        # Initialize Ibis backend
        self.ibis_conn = ibis.duckdb.from_connection(self._conn)

        # Cache for PRAGMA table metadata
        self._table_info_cache: dict[str, set[str]] = {}

        logger.info(
            "DuckDBStorageManager initialized (db=%s, checkpoints=%s)",
            "memory" if db_path is None else db_path,
            self.checkpoint_dir,
        )

    def _init_vector_extensions(self) -> None:
        """Install and load DuckDB VSS extension, and detect best search function."""
        # Enable HNSW index persistence for vector search
        # Requires 'vss' extension to be loaded first
        try:
            self._conn.execute("INSTALL vss; LOAD vss;")
            self._conn.execute("SET hnsw_enable_experimental_persistence=true")
            self._vss_function = self.detect_vss_function()
        except (duckdb.Error, RuntimeError) as exc:
            logger.warning("VSS extension unavailable: %s", exc)
            self._vss_function = None

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

    def get_vector_function_name(self) -> str | None:
        """Return the detected VSS search function name (vss_search or vss_match), or None."""
        return self._vss_function

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
            # Write checkpoint to parquet
            parquet_path = self.checkpoint_dir / f"{name}.parquet"
            parquet_path.parent.mkdir(parents=True, exist_ok=True)

            logger.debug("Writing checkpoint: %s", parquet_path)
            table.to_parquet(str(parquet_path))

            # Load into DuckDB from parquet (use quoted identifier to prevent SQL injection)
            quoted_name = quote_identifier(name)
            if mode == "replace":
                sql = f"CREATE OR REPLACE TABLE {quoted_name} AS SELECT * FROM read_parquet('{parquet_path}')"
            else:  # append
                # Create table if not exists, then insert
                sql = f"""
                    CREATE TABLE IF NOT EXISTS {quoted_name} AS SELECT * FROM read_parquet('{parquet_path}') WHERE 1=0;
                    INSERT INTO {quoted_name} SELECT * FROM read_parquet('{parquet_path}')
                """

            self._conn.execute(sql)
            logger.info("Table '%s' written with checkpoint (%s)", name, mode)

        # Direct write without checkpoint (faster but no persistence)
        elif mode == "replace":
            # Use Ibis to_sql for direct write
            # Note: This requires executing the table first
            dataframe = table.execute()
            self._conn.register(name, dataframe)
            logger.info("Table '%s' written without checkpoint (%s)", name, mode)
        else:
            msg = "Append mode requires checkpoint=True"
            raise ValueError(msg)

    def persist_atomic(self, table: Table, name: str, schema: ibis.Schema | None = None) -> None:
        """Persist an Ibis table to a DuckDB table atomically using a transaction.

        This preserves existing table properties (like indexes) by performing a
        DELETE + INSERT transaction instead of dropping and recreating the table.
        """
        if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", name):
            msg = "target_table must be a valid DuckDB identifier"
            raise ValueError(msg)

        target_schema = schema or IR_MESSAGE_SCHEMA
        schemas.create_table_if_not_exists(self._conn, name, target_schema)

        quoted_table = quote_identifier(name)
        column_list = ", ".join(quote_identifier(col) for col in target_schema.names)
        temp_view = f"_egregora_persist_{uuid.uuid4().hex}"

        try:
            # Create temp view from table expression
            self._conn.create_view(temp_view, table.to_pyarrow(), overwrite=True)
            quoted_view = quote_identifier(temp_view)

            self._conn.execute("BEGIN TRANSACTION")
            try:
                self._conn.execute(f"DELETE FROM {quoted_table}")
                self._conn.execute(
                    f"INSERT INTO {quoted_table} ({column_list}) SELECT {column_list} FROM {quoted_view}"
                )
                self._conn.execute("COMMIT")
            except Exception:
                logger.exception("Transaction failed during DuckDB persistence, rolling back")
                self._conn.execute("ROLLBACK")
                raise
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

            self._table_info_cache[cache_key] = {row[0] for row in rows}

        return self._table_info_cache[cache_key]

    # ==================================================================
    # Sequence helpers
    # ==================================================================

    def ensure_sequence(self, name: str, *, start: int = 1) -> None:
        """Create a sequence if it does not exist."""
        quoted_name = quote_identifier(name)
        self.conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {quoted_name} START {int(start)}")

    def get_sequence_state(self, name: str) -> SequenceState | None:
        """Return metadata describing the current state of ``name``."""
        row = self.conn.execute(
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
        column_default = self.conn.execute(
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
            self.conn.execute(
                f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_column} SET DEFAULT {desired_default}"
            )

    def sync_sequence_with_table(self, sequence_name: str, *, table: str, column: str) -> None:
        """Advance ``sequence_name`` so it is ahead of ``table.column``."""
        if not self.table_exists(table):
            return

        quoted_table = quote_identifier(table)
        quoted_column = quote_identifier(column)
        max_row = self.conn.execute(f"SELECT MAX({quoted_column}) FROM {quoted_table}").fetchone()
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

        cursor = self.conn.execute("SELECT nextval(?) FROM range(?)", [sequence_name, count])
        return [int(row[0]) for row in cursor.fetchall()]

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

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Context manager exit - closes connection."""
        self.close()

    # ==================================================================
    # Vector backend helpers (Consolidated)
    # ==================================================================

    def install_vss_extensions(self) -> bool:
        try:
            self._conn.execute("INSTALL vss")
            self._conn.execute("LOAD vss")
        except (duckdb.Error, RuntimeError) as exc:
            logger.warning("VSS extension unavailable: %s", exc)
            return False
        return True

    def detect_vss_function(self) -> str:
        try:
            rows = self._conn.execute("SELECT name FROM pragma_table_functions()").fetchall()
        except duckdb.Error as exc:
            logger.debug("Unable to inspect table functions: %s", exc)
            return "vss_search"
        function_names = {str(row[0]).lower() for row in rows if row}
        if "vss_search" in function_names:
            return "vss_search"
        if "vss_match" in function_names:
            logger.debug("Using vss_match table function for ANN queries")
            return "vss_match"
        logger.debug("No VSS table function detected; defaulting to vss_search")
        return "vss_search"

    def drop_index(self, name: str) -> None:
        quoted = quote_identifier(name)
        self._conn.execute(f"DROP INDEX IF EXISTS {quoted}")

    def row_count(self, table_name: str) -> int:
        if not self.table_exists(table_name):
            return 0
        quoted = quote_identifier(table_name)
        row = self._conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def create_hnsw_index(self, *, table_name: str, index_name: str, column: str = "embedding") -> bool:
        quoted_table = quote_identifier(table_name)
        quoted_index = quote_identifier(index_name)
        try:
            self._conn.execute(
                f"""
                CREATE INDEX {quoted_index}
                ON {quoted_table}
                USING HNSW ({column})
                WITH (metric = 'cosine')
                """
            )
            logger.info("Created HNSW index %s on %s.%s", index_name, table_name, column)
        except duckdb.Error as exc:
            logger.warning("Skipping HNSW index creation: %s", exc)
            return False
        return True


def temp_storage() -> DuckDBStorageManager:
    """Create temporary in-memory storage manager.

    Returns:
        DuckDBStorageManager with in-memory database

    Example:
        >>> with temp_storage() as storage:
        ...     storage.write_table(my_table, "temp")
        ...     result = storage.read_table("temp")

    """
    return DuckDBStorageManager(db_path=None, checkpoint_dir=Path("/tmp/.egregora-temp"))  # noqa: S108


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
    "combine_with_enrichment_rows",
    "duckdb_backend",
    "quote_identifier",
    "temp_storage",
]
