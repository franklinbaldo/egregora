"""Database initialization - create all tables at pipeline start.

This module provides simple, explicit database initialization using dynamically
generated SQL DDL from the single source of truth (IR_MESSAGE_SCHEMA).

All tables are created at the beginning of the pipeline, ensuring consistent schema
throughout the entire pipeline execution.

Design principles:
- Python schema (IR_MESSAGE_SCHEMA) is single source of truth
- SQL DDL is generated dynamically at runtime
- Initialize once at pipeline start
- No schema conversion/migration during pipeline execution
- Simple and explicit
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from egregora.database.validation import generate_ir_sql_ddl

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)


def initialize_database(backend: BaseBackend) -> None:
    """Initialize all database tables by executing dynamically generated SQL DDL.

    The SQL is generated from IR_MESSAGE_SCHEMA in validation.py, which is the
    single source of truth for the IR schema definition.

    Args:
        backend: Ibis backend (DuckDB, Postgres, etc.)

    Raises:
        Exception: If SQL execution fails

    Example:
        >>> import ibis
        >>> backend = ibis.duckdb.connect("pipeline.db")
        >>> initialize_database(backend)
        >>> # All tables now exist and can be used

    """
    logger.info("Initializing database tables...")

    # Generate SQL DDL from IR_MESSAGE_SCHEMA (single source of truth)
    sql_content = generate_ir_sql_ddl()
    logger.debug("Executing generated IR schema DDL")

    # DuckDB backend has .con.execute() for raw SQL
    if hasattr(backend, "con"):
        backend.con.execute(sql_content)
    else:
        # Fallback for other backends
        backend.raw_sql(sql_content)

    logger.info("✓ Database tables initialized successfully")


__all__ = ["initialize_database"]
