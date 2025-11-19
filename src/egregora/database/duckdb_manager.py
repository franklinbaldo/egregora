"""Centralized storage manager for DuckDB + Ibis operations.

Provides a unified interface for reading/writing tables with automatic
checkpointing.

This module implements Priority C.2 from the Architecture Roadmap:
centralized DuckDB access to eliminate raw SQL and provide consistent
checkpoint management across pipeline stages.

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

import contextlib
import logging
import re
from pathlib import Path
from typing import Literal

import duckdb
import ibis
from ibis.expr.types import Table

from egregora.database.views import ViewBuilder

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


class DuckDBStorageManager:
    """Centralized DuckDB connection + Ibis helpers.

    Manages database connections, table I/O, and automatic checkpointing
    for pipeline stages. View transformations are provided as callables
    (see :mod:`egregora.database.views`).

    Attributes:
        db_path: Path to DuckDB file (or None for in-memory)
        conn: Raw DuckDB connection
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
        self.conn = duckdb.connect(db_str)

        # Initialize Ibis backend
        self.ibis_conn = ibis.duckdb.from_connection(self.conn)

        logger.info(
            "DuckDBStorageManager initialized (db=%s, checkpoints=%s)",
            "memory" if db_path is None else db_path,
            self.checkpoint_dir,
        )

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

            self.conn.execute(sql)
            logger.info("Table '%s' written with checkpoint (%s)", name, mode)

        # Direct write without checkpoint (faster but no persistence)
        elif mode == "replace":
            # Use Ibis to_sql for direct write
            # Note: This requires executing the table first
            df = table.execute()
            self.conn.register(name, df)
            logger.info("Table '%s' written without checkpoint (%s)", name, mode)
        else:
            msg = "Append mode requires checkpoint=True"
            raise ValueError(msg)

    def execute_view(
        self,
        view_name: str,
        builder: ViewBuilder,
        input_table: str,
        *,
        checkpoint: bool = True,
    ) -> Table:
        """Execute view builder and optionally materialize result.

        Args:
            view_name: Name for output table
            builder: Callable that transforms an Ibis table
            input_table: Name of input table
            checkpoint: If True, save result to table

        Returns:
            Result of view transformation

        Example:
            >>> from egregora.database.views import COMMON_VIEWS
            >>> chunks_builder = COMMON_VIEWS["chunks"]
            >>> result = storage.execute_view(
            ...     "chunks_materialized",
            ...     chunks_builder,
            ...     "conversations"
            ... )

        """
        # Read input table
        input_ir = self.read_table(input_table)

        # Execute view transformation
        result = builder(input_ir)

        # Optionally materialize
        if checkpoint:
            self.write_table(result, view_name)
            logger.info("View '%s' materialized from '%s'", view_name, input_table)

        return result

    def drop_table(self, name: str) -> None:
        """Drop a table if it exists."""
        quoted_name = quote_identifier(name)
        self.conn.execute(f"DROP TABLE IF EXISTS {quoted_name}")
        logger.info("Dropped table if existed: %s", name)

    def table_exists(self, name: str) -> bool:
        """Check if table exists in database.

        Args:
            name: Table name

        Returns:
            True if table exists, False otherwise

        """
        tables = self.conn.execute(
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
        tables = self.conn.execute(
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
            self.conn.execute(f"DROP VIEW IF EXISTS {quoted_name}")
        with contextlib.suppress(Exception):
            self.conn.execute(f"DROP TABLE IF EXISTS {quoted_name}")
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
        self.conn.close()
        logger.info("DuckDBStorageManager closed")

    def __enter__(self) -> "DuckDBStorageManager":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Context manager exit - closes connection."""
        self.close()


# ============================================================================
# Convenience Functions (Phase 2.2: Consolidated from connection.py)
# ============================================================================


def temp_storage() -> DuckDBStorageManager:
    """Create temporary in-memory storage manager.

    Returns:
        DuckDBStorageManager with in-memory database

    Example:
        >>> with temp_storage() as storage:
        ...     storage.write_table(my_table, "temp")
        ...     result = storage.read_table("temp")

    """
    return DuckDBStorageManager(db_path=None, checkpoint_dir=Path("/tmp/.egregora-temp"))


@contextlib.contextmanager
def duckdb_backend():
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
    "duckdb_backend",
    "temp_storage",
]
