"""V3 utility functions - independent of V2."""
from pathlib import Path

# V2 Compatibility Shim: slugify and related exceptions are now defined in this
# module. The V2 `egregora.utils.text` module re-exports them from here.


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


# --- V2 Compatibility ---
# The following slugify logic is ported from V2 to consolidate text utilities
# in the V3 core. V2's text_utils now acts as a compatibility shim.

from unicodedata import normalize

from pymdownx.slugs import slugify as _md_slugify
from egregora.exceptions import EgregoraError


# Slugify-specific exceptions (defined here as they're utils-level)
class SlugifyError(EgregoraError):
    """Base exception for slugify-related errors."""


class InvalidInputError(SlugifyError):
    """Raised when the input to a function is invalid."""


# Pre-configure a slugify instance for reuse.
slugify_lower = _md_slugify(case="lower", separator="-")
slugify_case = _md_slugify(separator="-")


def slugify(text: str, max_len: int = 60, *, lowercase: bool = True) -> str:
    """Convert text to a safe URL-friendly slug using MkDocs/Python Markdown semantics."""
    if text is None:
        raise InvalidInputError("Input text cannot be None")

    # Normalize Unicode to ASCII using NFKD (preserves transliteration).
    normalized = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    # Choose the appropriate pre-configured slugifier.
    slugifier = slugify_lower if lowercase else slugify_case
    slug = slugifier(normalized, sep="-")

    # Fallback for empty slugs, truncate, and clean up trailing hyphens.
    slug = slug or "post"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")

    return slug
