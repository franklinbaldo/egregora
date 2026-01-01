"""V3 utility functions - independent of V2."""

import re
from unicodedata import normalize

from pymdownx.slugs import slugify as _md_slugify


# Pre-configure slugify instances for reuse, matching V2 behavior.
slugify_lower = _md_slugify(case="lower", separator="-")
slugify_case = _md_slugify(separator="-")


def slugify(text: str, max_len: int = 60, *, lowercase: bool = True) -> str:
    """Convert text to a safe URL-friendly slug using MkDocs/Python Markdown semantics.

    V3 implementation that is compatible with V2.
    Uses pymdownx.slugs directly for consistent behavior.

    Args:
        text: Input text to slugify
        max_len: Maximum length of output slug (default 60)
        lowercase: Whether to lowercase the slug (default True)

    Returns:
        Safe slug string suitable for filenames and URLs
    """
    if text is None:
        return ""

    # Normalize Unicode to ASCII using NFKD (preserves transliteration).
    normalized = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    # Choose the appropriate pre-configured slugifier.
    slugifier = slugify_lower if lowercase else slugify_case
    slug = slugifier(normalized, sep="-")

    # V2 used 'post' as a fallback, V3 used 'untitled'. Let's stick with V2's for now.
    slug = slug or "post"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")

    return slug


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
