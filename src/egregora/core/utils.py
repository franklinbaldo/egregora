"""V3 utility functions - independent of V2."""
from pathlib import Path

# Explicitly import from the canonical V2 utility
from egregora.utils.text import slugify


class V3UtilsError(Exception):
    """Base exception for V3 utilities."""


class PathTraversalError(V3UtilsError):
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

    Examples:
        >>> base = Path("/output")
        >>> safe_path_join(base, "posts", "2025-01-01-hello.md")
        PosixPath('/output/posts/2025-01-01-hello.md')
        >>> safe_path_join(base, "../../etc/passwd")  # doctest: +SKIP
        Traceback (most recent call last):
        ...
        PathTraversalError: Path escaped output directory

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
