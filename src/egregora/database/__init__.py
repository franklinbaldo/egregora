"""Database utilities and schemas for Egregora."""

from egregora.database.connection import duckdb_backend
from egregora.schema import MESSAGE_SCHEMA

__all__ = ["MESSAGE_SCHEMA", "duckdb_backend"]
