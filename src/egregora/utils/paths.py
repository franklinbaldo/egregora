"""Path safety utilities for secure file operations."""

from pathlib import Path
from unicodedata import normalize

from pymdownx.slugs import slugify as _md_slugify


class PathTraversalError(Exception):
    """Raised when a path would escape its intended directory."""


def slugify(text: str, max_len: int = 60, *, lowercase: bool = True) -> str:
    """Convert text to a safe URL-friendly slug using MkDocs/Python Markdown semantics.

    Produces ASCII-only, hyphen-separated slugs matching MkDocs tab/heading behavior.

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
        'etc-passwd'
        >>> slugify("A" * 100, max_len=20)
        'aaaaaaaaaaaaaaaaaaaa'

    """
    normalized = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slugifier = _md_slugify(case="lower" if lowercase else None, separator="-")
    slug = slugifier(normalized, sep="-")
    if not slug:
        return "post"
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
    base_resolved = base_dir.resolve()
    candidate = base_resolved
    for part in parts:
        part_path = Path(part)
        if part_path.is_absolute():
            msg = f"Absolute paths not allowed: {part}"
            raise PathTraversalError(msg)
        candidate = candidate.joinpath(part_path)

    try:
        candidate_resolved = candidate.resolve()
    except OSError as exc:  # pragma: no cover - defensive
        msg = f"Failed to resolve path {candidate}: {exc}"
        raise PathTraversalError(msg) from exc

    try:
        candidate_resolved.relative_to(base_resolved)
    except ValueError:
        msg = f"Path traversal detected: joining {parts} to {base_dir} would escape base directory"
        raise PathTraversalError(msg)

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
