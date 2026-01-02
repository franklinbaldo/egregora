"""V3 utility functions - independent of V2."""
from pathlib import Path
import re
from unicodedata import normalize
from pymdownx.slugs import slugify as _md_slugify

class PathTraversalError(Exception):
    """Raised when a path would escape its intended directory."""

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
    if text is None:
        return ""

    # Pre-process to handle characters slugify would strip but we want as separators
    text = text.replace(":", "-")

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

DEFAULT_MAX_CHARS = 800
DEFAULT_CHUNK_OVERLAP = 200


def simple_chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Simple chunking: split text into ~max_chars chunks with overlap."""
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    overlap = min(overlap, max_chars // 2)
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    # Overlap buffer
    overlap_words: list[str] = []
    overlap_len = 0

    for w in words:
        word_len = len(w) + 1  # +1 for space

        if current_len + word_len > max_chars and current:
            chunk_text = " ".join(current)
            chunks.append(chunk_text)

            # Build overlap from end of current chunk
            overlap_words = []
            overlap_len = 0
            for overlap_word in reversed(current):
                overlap_word_len = len(overlap_word) + 1
                if overlap_len + overlap_word_len <= overlap:
                    overlap_words.append(overlap_word)
                    overlap_len += overlap_word_len
                else:
                    break
            overlap_words.reverse()

            current = overlap_words.copy()
            current_len = overlap_len

        current.append(w)
        current_len += word_len

    if current:
        chunks.append(" ".join(current))

    return chunks
