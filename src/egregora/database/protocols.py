"""Protocol definitions for database abstraction layer.

This module defines protocols that abstract away specific database implementations,
allowing the application to work with different backends (DuckDB, Postgres, etc.)
without coupling high-level logic to implementation details.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, Protocol

import ibis
from ibis.expr.types import Table


class StorageProtocol(Protocol):
    """Protocol for database storage operations.

    Defines the interface that all storage backends must implement,
    allowing the application to work with any database that supports
    Ibis operations.
    """

    @property
    def checkpoint_dir(self) -> Path:
        """Get the directory for parquet checkpoints."""
        ...

    def read_table(self, name: str) -> Table:
        """Read table as Ibis expression.

        Args:
            name: Table name

        Returns:
            Ibis table expression

        Raises:
            ValueError: If table doesn't exist
        """
        ...

    def write_table(
        self,
        table: Table,
        name: str,
        mode: Literal["replace", "append"] = "replace",
        *,
        checkpoint: bool = True,
    ) -> None:
        """Write Ibis table to storage.

        Args:
            table: Ibis table expression to write
            name: Destination table name
            mode: Write mode ("replace" or "append")
            checkpoint: If True, save parquet checkpoint to disk
        """
        ...

    def persist_atomic(
        self,
        table: Table,
        name: str,
        schema: ibis.Schema | None = None,
    ) -> None:
        """Persist an Ibis table atomically using a transaction.

        This preserves existing table properties (like indexes) by performing a
        DELETE + INSERT transaction instead of dropping and recreating the table.

        Args:
            table: Ibis table to persist
            name: Target table name
            schema: Optional schema to validate against
        """
        ...

    def table_exists(self, name: str) -> bool:
        """Check if table exists.

        Args:
            name: Table name

        Returns:
            True if table exists, False otherwise
        """
        ...

    def list_tables(self) -> list[str]:
        """List all tables in storage.

        Returns:
            Sorted list of table names
        """
        ...

    def drop_table(self, name: str, *, checkpoint_too: bool = False) -> None:
        """Drop table from storage.

        Args:
            name: Table name
            checkpoint_too: If True, also delete parquet checkpoint
        """
        ...

    def get_table_columns(self, table_name: str, *, refresh: bool = False) -> set[str]:
        """Get column names for a table.

        Args:
            table_name: Table name
            refresh: If True, bypass cache

        Returns:
            Set of column names
        """
        ...

    def execute_query(self, sql: str, params: list | None = None) -> list:
        """Execute a raw SQL query and return all results.

        Args:
            sql: SQL query string
            params: Optional list of parameters for prepared statement

        Returns:
            List of result tuples
        """
        ...

    def execute_query_single(self, sql: str, params: list | None = None) -> tuple | None:
        """Execute a raw SQL query and return a single result row.

        Args:
            sql: SQL query string
            params: Optional list of parameters

        Returns:
            Single result tuple or None
        """
        ...

    def close(self) -> None:
        """Close storage connection."""
        ...

    @contextmanager
    def connection(self) -> Any:
        """Yield the underlying database connection.

        This is an escape hatch for code that needs direct access to the
        database. Prefer using the protocol methods when possible.
        """
        ...


class VectorStorageProtocol(Protocol):
    """Protocol for vector storage operations.

    Defines operations specific to vector databases and similarity search.
    """

    def get_vector_function_name(self) -> str | None:
        """Return the vector search function name (e.g., 'vss_search', 'vss_match'), or None."""
        ...

    def create_hnsw_index(
        self,
        *,
        table_name: str,
        index_name: str,
        column: str = "embedding",
    ) -> bool:
        """Create an HNSW index for vector similarity search.

        Args:
            table_name: Table containing vectors
            index_name: Name for the index
            column: Column containing vector embeddings

        Returns:
            True if index created successfully, False otherwise
        """
        ...

    def drop_index(self, name: str) -> None:
        """Drop an index.

        Args:
            name: Index name
        """
        ...

    def row_count(self, table_name: str) -> int:
        """Get row count for a table.

        Args:
            table_name: Table name

        Returns:
            Number of rows
        """
        ...


class SequenceStorageProtocol(Protocol):
    """Protocol for sequence operations.

    Defines operations for managing database sequences (auto-incrementing IDs).
    """

    def ensure_sequence(self, name: str, *, start: int = 1) -> None:
        """Create a sequence if it does not exist.

        Args:
            name: Sequence name
            start: Starting value
        """
        ...

    def next_sequence_value(self, sequence_name: str) -> int:
        """Return the next value from a sequence.

        Args:
            sequence_name: Sequence name

        Returns:
            Next sequence value
        """
        ...

    def next_sequence_values(self, sequence_name: str, *, count: int = 1) -> list[int]:
        """Return multiple sequential values from a sequence.

        Args:
            sequence_name: Sequence name
            count: Number of values to return

        Returns:
            List of sequence values
        """
        ...


__all__ = [
    "StorageProtocol",
    "VectorStorageProtocol",
    "SequenceStorageProtocol",
]
