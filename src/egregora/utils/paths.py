"""Path safety utilities for secure file operations."""

from pathlib import Path

from slugify import slugify as _slugify
from werkzeug.utils import safe_join as _werkzeug_safe_join


class PathTraversalError(Exception):
    """Raised when a path would escape its intended directory."""


def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a safe URL-friendly slug using python-slugify.

    Uses the industry-standard python-slugify library with Unicode transliteration
    support (100M+ downloads). Handles Cyrillic, Greek, Arabic, CJK, and more.

    Args:
        text: Input text to slugify
        max_len: Maximum length of output slug (default 60)

    Returns:
        Safe slug string suitable for filenames

    Examples:
        >>> slugify("Hello World!")
        'hello-world'
        >>> slugify("Café à Paris")
        'cafe-a-paris'
        >>> slugify("Привет мир")
        'privet-mir'
        >>> slugify("../../etc/passwd")
        'etc-passwd'
        >>> slugify("A" * 100, max_len=20)
        'aaaaaaaaaaaaaaaaaaaa'

    """
    slug = _slugify(text, max_length=max_len, separator="-")
    return slug if slug else "post"


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
    normalized_parts = []
    min_windows_abs_path_len = 3
    for part in parts:
        if len(part) >= min_windows_abs_path_len and part[1:3] == ":\\":
            msg = f"Absolute Windows paths not allowed: {part}"
            raise PathTraversalError(msg)
        normalized_parts.append(part.replace("\\", "/"))
    base_str = str(base_dir.resolve())
    try:
        result_str = _werkzeug_safe_join(base_str, *normalized_parts)
    except Exception as exc:
        msg = f"Path traversal detected: joining {parts} to {base_dir} would escape base directory"
        raise PathTraversalError(msg) from exc
    if result_str is None:
        msg = f"Path traversal detected: joining {parts} to {base_dir} would escape base directory"
        raise PathTraversalError(msg)
    return Path(result_str)


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
