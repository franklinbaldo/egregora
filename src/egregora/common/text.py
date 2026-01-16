"""Text-related utilities, including slugification."""

from unicodedata import normalize

from pymdownx.slugs import slugify as _md_slugify

from egregora.exceptions import EgregoraError

# Pre-configure a slugify instance for reuse.
# This is more efficient than creating a new slugifier on each call.
slugify_lower = _md_slugify(case="lower", separator="-")
slugify_case = _md_slugify(separator="-")


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

    """
    if text is None:
        msg = "Input text cannot be None"
        raise InvalidInputError(msg)

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


# Slugify-specific exceptions (defined here as they're utils-level)
class SlugifyError(EgregoraError):
    """Base exception for slugify-related errors."""


class InvalidInputError(SlugifyError):
    """Raised when the input to a function is invalid."""
