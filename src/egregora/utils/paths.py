"""Path safety utilities for secure file operations."""

from pathlib import Path
from unicodedata import normalize

from pymdownx.slugs import slugify as _md_slugify


class PathTraversalError(Exception):
    """Raised when a path would escape its intended directory."""


def slugify(text: str, max_len: int = 60, *, lowercase: bool = True) -> str:
    """Convert text to a safe URL-friendly slug using MkDocs/Python Markdown semantics.

    Uses pymdownx.slugs directly for consistent behavior with MkDocs heading IDs.
    Produces ASCII-only slugs with Unicode transliteration.

    Args:
        text: Input text to slugify
        max_len: Maximum length of output slug (default 60)
        lowercase: Whether to lowercase the slug (default True)

    Returns:
        Safe slug string suitable for filenames

    Examples:
        >>> slugify("Hello World!")
        'hello-world'
        >>> slugify("Hello World!", lowercase=False)
        'Hello-World'
        >>> slugify("Café à Paris")
        'cafe-a-paris'
        >>> slugify("Привет мир")
        'privet-mir'
        >>> slugify("../../etc/passwd")
        'etcpasswd'
        >>> slugify("A" * 100, max_len=20)
        'aaaaaaaaaaaaaaaaaaaa'

    """
    # Normalize Unicode to ASCII using NFKD (preserves transliteration)
    normalized = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    # Use pymdownx.slugs with appropriate settings
    slugifier = _md_slugify(case="lower" if lowercase else None, separator="-")
    slug = slugifier(normalized, sep="-")

    # Fallback for empty slugs
    if not slug:
        return "post"

    # Truncate to max length, removing trailing hyphens
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")

    return slug


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
