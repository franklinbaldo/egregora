"""Database utility functions."""

import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def resolve_db_uri(uri: str, site_root: Path) -> str:
    """Resolve database URI relative to site root.

    Handles special relative path syntax for DuckDB:
    - duckdb:///./path -> site_root/path
    - duckdb:///path -> /path (absolute) or path (relative to CWD)

    Args:
        uri: The Ibis connection URI
        site_root: The root directory of the site

    Returns:
        Resolved absolute URI string

    """
    if not uri:
        return uri

    parsed = urlparse(uri)
    if parsed.scheme == "duckdb" and not parsed.netloc:
        path_value = parsed.path
        if path_value and path_value not in {"/:memory:", ":memory:", "memory", "memory:"}:
            fs_path: Path
            if path_value.startswith("/./"):
                fs_path = (site_root / Path(path_value[3:])).resolve()
            else:
                fs_path = Path(path_value).resolve()

            fs_path.parent.mkdir(parents=True, exist_ok=True)

            if os.name == "nt":
                # Windows paths need to avoid the leading slash (duckdb:///C:/)
                # to prevent Ibis from prepending the current drive (C:/C:/).
                # Using duckdb:C:/... (one slash after scheme) works.
                return f"duckdb:{fs_path.as_posix()}"

            return f"duckdb://{fs_path}"

    return uri


def quote_identifier(identifier: str) -> str:
    """Quote a SQL identifier to prevent injection and handle special characters.

    Args:
        identifier: The identifier to quote (table name, column name, etc.)

    Returns:
        Properly quoted identifier safe for use in SQL

    Note:
        DuckDB uses double quotes for identifiers. Inner quotes are escaped by doubling.
        Example: my"table → "my""table"

    """
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def convert_ibis_table_to_list(table: Any) -> list[dict[str, Any]]:
    """Convert an Ibis table (or similar object) to a list of dictionaries safely.

    Handles various execution results from different Ibis backends:
    - PyArrow Table -> to_pylist()
    - Pandas DataFrame -> to_dict(orient="records")
    - List -> return as is

    Args:
        table: An Ibis table expression, executed result, or list.

    Returns:
        List of dictionaries representing the rows.

    """
    if isinstance(table, list):
        return table

    result = table
    # If it's an Ibis table expression, execute it
    if hasattr(table, "execute"):
        try:
            result = table.execute()
        except (AttributeError, TypeError):
            # If execution fails with specific errors, we might be dealing with a mock or raw object
            # Fall through to try conversion methods on the object itself.
            # CRITICAL: Do not catch generic Exception here; DB errors must propagate.
            logging.getLogger(__name__).debug(
                "Execution failed with AttributeError/TypeError in convert_ibis_table_to_list, falling back",
                exc_info=True,
            )

    # Handle PyArrow Table (has to_pylist)
    if hasattr(result, "to_pylist"):
        return result.to_pylist()

    # Handle Pandas DataFrame (has to_dict)
    if hasattr(result, "to_dict"):
        return result.to_dict(orient="records")

    # Fallback if result is already a list (some backends might return list)
    if isinstance(result, list):
        return result

    # Last resort fallback: check if the original object has conversion methods
    # (e.g. if execute() wasn't called or failed but methods exist on the object)
    if hasattr(table, "to_pylist"):
        return table.to_pylist()

    return []
