"""Database initialization - create all tables at pipeline start.

This module provides simple, explicit database initialization using SQL DDL files.
All tables are created at the beginning of the pipeline, ensuring consistent schema
throughout the entire pipeline execution.

Design principles:
- SQL DDL files define all schemas (no Python schema construction)
- Initialize once at pipeline start
- No schema conversion/migration during pipeline execution
- Simple and explicit
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def initialize_database(backend: BaseBackend) -> None:
    """Initialize all database tables by executing SQL schema files.

    Args:
        backend: Ibis backend (DuckDB, Postgres, etc.)

    Raises:
        FileNotFoundError: If schema files are missing
        Exception: If SQL execution fails

    Example:
        >>> import ibis
        >>> backend = ibis.duckdb.connect("pipeline.db")
        >>> initialize_database(backend)
        >>> # All tables now exist and can be used
    """
    logger.info("Initializing database tables...")

    # Execute IR messages schema
    ir_messages_sql = SCHEMAS_DIR / "ir_messages.sql"
    if not ir_messages_sql.exists():
        msg = f"Schema file not found: {ir_messages_sql}"
        raise FileNotFoundError(msg)

    sql_content = ir_messages_sql.read_text()
    logger.debug("Executing schema: %s", ir_messages_sql.name)

    # DuckDB backend has .con.execute() for raw SQL
    if hasattr(backend, "con"):
        backend.con.execute(sql_content)
    else:
        # Fallback for other backends
        backend.raw_sql(sql_content)

    logger.info("✓ Database tables initialized successfully")


__all__ = ["initialize_database"]
