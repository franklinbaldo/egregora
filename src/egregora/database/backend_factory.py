"""Database backend creation and validation factory.

This module handles the creation and validation of database connections for the pipeline,
abstracting the details of Ibis/DuckDB connection strings and resolution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import ibis

from egregora.config.settings import EgregoraConfig
from egregora.database.utils import resolve_db_uri


def validate_and_connect_db(value: str | None, setting_name: str, site_root: Path) -> tuple[str, Any]:
    """Validate database URI and connect to the backend.

    Args:
        value: Database URI string
        setting_name: Name of the setting for error messages
        site_root: Site root directory for resolving relative paths

    Returns:
        Tuple of (resolved_uri, backend_connection)

    Raises:
        ValueError: If the URI is invalid or empty.

    """
    if not value:
        msg = f"Database setting '{setting_name}' must be a non-empty connection URI."
        raise ValueError(msg)

    parsed = urlparse(value)
    if not parsed.scheme:
        msg = (
            f"Database setting '{setting_name}' must be provided as an Ibis-compatible connection "
            "URI (e.g. 'duckdb:///absolute/path/to/file.duckdb' or 'postgres://user:pass@host/db')."
        )
        raise ValueError(msg)

    if len(parsed.scheme) == 1 and value[1:3] in {":/", ":\\"}:
        msg = (
            f"Database setting '{setting_name}' looks like a filesystem path. Provide a full connection "
            "URI instead (see the database settings documentation)."
        )
        raise ValueError(msg)

    normalized_value = resolve_db_uri(value, site_root)
    return normalized_value, ibis.connect(normalized_value)


def create_pipeline_database(
    site_root: Path,
    config: EgregoraConfig,
) -> tuple[str, Any]:
    """Create the main database backend for the pipeline.

    Args:
        site_root: Site root directory
        config: Egregora configuration

    Returns:
        Tuple of (resolved_uri, backend_connection)

    """
    return validate_and_connect_db(config.database.pipeline_db, "database.pipeline_db", site_root)
