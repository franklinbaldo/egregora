"""Filesystem utility functions.

MODERN (Phase 3): Consolidated filesystem helpers to reduce boilerplate.
"""

from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist, with proper parent creation.

    This is a convenience wrapper around mkdir that sets the standard
    options for ensuring a directory exists without errors.

    Args:
        path: Directory path to create

    Returns:
        The same path (for chaining)

    Examples:
        >>> ensure_dir(Path("output/posts"))
        PosixPath('output/posts')

        >>> # Chaining example
        >>> output_file = ensure_dir(Path("output/data")) / "results.csv"

    """
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["ensure_dir"]
