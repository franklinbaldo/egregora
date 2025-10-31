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

    Normalizes both forward and backward slashes to prevent cross-platform
    path traversal attacks. On POSIX systems, backslashes are valid filename
    characters, so we normalize them to forward slashes before validation.

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
        Protects against both Unix (/) and Windows (\\) path traversal on all platforms.
        Backslashes are normalized to forward slashes before path resolution to prevent
        POSIX systems from treating them as literal filename characters.
    """
    if not base_dir.is_absolute():
        base_dir = base_dir.resolve()

    # Normalize path separators: replace backslashes with forward slashes
    # This prevents POSIX systems from treating backslashes as filename characters
    normalized_parts = [part.replace("\\", "/") for part in parts]

    # Join the normalized parts
    result = base_dir.joinpath(*normalized_parts).resolve()

    # Ensure result is within base_dir
    try:
        result.relative_to(base_dir)
    except ValueError:
        raise PathTraversalError(
            f"Path escaped output directory: {result} is not within {base_dir}"
        )

    return result
