"""Path safety utilities for secure file operations."""

from pathlib import Path

from slugify import slugify as _slugify
from werkzeug.exceptions import NotFound as _WerkzeugNotFound
from werkzeug.exceptions import SecurityError as _WerkzeugSecurityError
from werkzeug.utils import safe_join as _werkzeug_safe_join


class PathTraversalError(Exception):
    """Raised when a path would escape its intended directory."""

    pass


def slugify(text: str, max_len: int = 60) -> str:
    """
    Convert text to a safe URL-friendly slug using python-slugify.

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
    """
    Safely join path parts and ensure result stays within base_dir.

    Uses werkzeug.utils.safe_join, the industry-standard path security
    function from the Flask/Werkzeug ecosystem (100M+ downloads). Protects
    against path traversal attacks on all platforms.

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
        >>> safe_path_join(base, "..\\\\..\\\\windows\\\\system32")  # doctest: +SKIP
        Traceback (most recent call last):
        ...
        PathTraversalError: Path escaped output directory

    Security:
        Uses werkzeug.utils.safe_join (industry standard since 2007).
        Protects against Unix (/) and Windows (\\) path traversal on all platforms.
        Werkzeug normalizes path separators and validates containment automatically.

    References:
        https://werkzeug.palletsprojects.com/en/3.0.x/utils/#werkzeug.utils.safe_join
    """
    # Convert Path to string for werkzeug compatibility
    base_str = str(base_dir.resolve())

    try:
        # werkzeug.utils.safe_join returns None on older versions and raises on >=3.0
        result_str = _werkzeug_safe_join(base_str, *parts)
    except (_WerkzeugNotFound, _WerkzeugSecurityError) as exc:
        raise PathTraversalError(
            f"Path traversal detected: joining {parts} to {base_dir} would escape base directory"
        ) from exc

    if result_str is None:
        # Path traversal attempt detected (Werkzeug < 3.0)
        raise PathTraversalError(
            f"Path traversal detected: joining {parts} to {base_dir} would escape base directory"
        )

    return Path(result_str)
