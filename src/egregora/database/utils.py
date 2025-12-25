
import shutil
import subprocess
from functools import lru_cache
from urllib.parse import urlparse
from pathlib import Path

@lru_cache(maxsize=1)
def get_git_commit_sha() -> str | None:
    """Get current git commit SHA for reproducibility tracking.

    Returns:
        Git commit SHA (e.g., "a1b2c3d4..."), or None if not in git repo

    """
    git_path = shutil.which("git")
    if not git_path:
        return None

    try:
        # S603 is ignored because we're running git, which we assume is safe in this context.
        result = subprocess.run(  # noqa: S603
            [git_path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None

def quote_identifier(name: str) -> str:
    """Quote SQL identifier to prevent keyword collisions."""
    return f'"{name.replace("\"", "\"\"")}"'

def resolve_db_uri(uri: str, base_dir: Path) -> str:
    """Resolve relative DuckDB URIs to absolute paths."""
    parsed = urlparse(uri)
    if parsed.scheme == "duckdb" and parsed.path.startswith("/./"):
        # Resolve path relative to base_dir
        relative_path = parsed.path[3:]
        absolute_path = base_dir.joinpath(relative_path).resolve()
        return f"duckdb:///{absolute_path}"
    return uri
