"""Path safety utilities for secure file operations."""

from pathlib import Path
from shared.slugify import slugify


class PathTraversalError(Exception):
    """Raised when a path would escape its intended directory."""


def safe_path_join(base_dir: Path, *parts: str) -> Path:
    r"""Safely join path parts and ensure result stays within base_dir.

    Protects against path traversal attacks on all platforms by normalizing
    path separators and validating that the resolved path is contained within
    the base directory.

    Args:
        base_dir: Base directory that result must stay within
        *parts: Path parts to join

    Returns:
        Resolved path guaranteed to be within base_dir

    Raises:
        PathTraversalError: If resulting path would escape base_dir
    """
    if any(Path(part).is_absolute() for part in parts):
        absolute_part = next(part for part in parts if Path(part).is_absolute())
        msg = f"Absolute paths not allowed: {absolute_part}"
        raise PathTraversalError(msg)

    base_resolved = base_dir.resolve()
    candidate_path = base_resolved.joinpath(*parts)

    try:
        candidate_resolved = candidate_path.resolve()
        candidate_resolved.relative_to(base_resolved)
    except (ValueError, OSError) as err:
        msg = f"Path traversal detected: joining {parts} to {base_dir} would escape base directory"
        raise PathTraversalError(msg) from err

    return candidate_resolved
