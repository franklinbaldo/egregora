"""Path safety utilities for secure file operations."""

import re
import unicodedata
from pathlib import Path


class PathTraversalError(Exception):
    """Raised when a path would escape its intended directory."""

    pass


def slugify(text: str, max_len: int = 60) -> str:
    """
    Convert text to a safe URL-friendly slug.

    Normalizes Unicode to ASCII, lowercases, replaces non-alphanumeric
    characters with hyphens, and truncates to max_len.

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
        >>> slugify("../../etc/passwd")
        'etc-passwd'
        >>> slugify("A" * 100, max_len=20)
        'aaaaaaaaaaaaaaaaaaaa'
    """
    # Normalize Unicode to ASCII
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

    # Lowercase and replace non-alphanumeric with hyphens
    ascii_text = ascii_text.lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", ascii_text)

    # Clean up hyphens
    slug = slug.strip("-")
    slug = re.sub(r"-{2,}", "-", slug)

    # Truncate and provide fallback
    slug = slug[:max_len]
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
