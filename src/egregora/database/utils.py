"""Database utility functions."""

import os
from pathlib import Path
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
