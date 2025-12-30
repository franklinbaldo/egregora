"""Database utility functions."""

from pathlib import Path
from urllib.parse import urlparse

from egregora.database.duckdb_manager import DuckDBStorageManager


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
            return f"duckdb://{fs_path}"

    return uri


def get_simple_storage(db_path: Path) -> DuckDBStorageManager:
    """Get a simple DuckDB storage instance for CLI queries.

    Args:
        db_path: Path to the DuckDB database file

    Returns:
        SimpleDuckDBStorage instance for executing queries

    Note:
        This is used by CLI read commands that don't need the full Ibis stack.

    """
    return DuckDBStorageManager(db_path)
