"""Database utilities for pipeline stages.

Provides context managers and helpers for working with DuckDB/Ibis backends.
"""

import logging
from contextlib import contextmanager
from typing import Generator

import duckdb
import ibis

logger = logging.getLogger(__name__)


@contextmanager
def duckdb_backend() -> Generator[ibis.BaseBackend, None, None]:
    """
    Context manager for temporary DuckDB backend.

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
