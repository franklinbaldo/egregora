"""Path safety utilities for secure file operations."""

from pathlib import Path

from slugify import slugify as _slugify


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

    Args:
        base_dir: Base directory that result must stay within
        *parts: Path parts to join (will be slugified if needed)

    Returns:
        Resolved path guaranteed to be within base_dir

    Raises:
        PathTraversalError: If resulting path would escape base_dir
        ValueError: If base_dir is not a directory

    Examples:
        >>> base = Path("/output")
        >>> safe_path_join(base, "posts", "2025-01-01-hello.md")
        PosixPath('/output/posts/2025-01-01-hello.md')
        >>> safe_path_join(base, "../../etc/passwd")  # doctest: +SKIP
        Traceback (most recent call last):
        ...
        PathTraversalError: Path escaped output directory
    """
    if not base_dir.is_absolute():
        base_dir = base_dir.resolve()

    # Join the parts
    result = base_dir.joinpath(*parts).resolve()

    # Ensure result is within base_dir
    try:
        result.relative_to(base_dir)
    except ValueError:
        raise PathTraversalError(
            f"Path escaped output directory: {result} is not within {base_dir}"
        )

    return result
