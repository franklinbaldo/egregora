"""General text utility functions."""

import re
from unicodedata import normalize


def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a safe URL-friendly slug.

    V3 implementation - does not depend on V2 or external slugifiers.

    Args:
        text: Input text to slugify
        max_len: Maximum length of output slug (default 60)

    Returns:
        Safe slug string suitable for filenames and URLs

    Examples:
        >>> slugify("Hello World")
        'hello-world'
        >>> slugify("Café")
        'cafe'
        >>> slugify("A" * 100, max_len=20)
        'aaaaaaaaaaaaaaaaaaaa'

    """
    # Normalize unicode (NFD) and convert to ASCII
    normalized = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    # Lowercase
    normalized = normalized.lower()

    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", normalized)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Collapse consecutive hyphens
    slug = re.sub(r"-+", "-", slug)

    # Return default if empty
    if not slug:
        return "untitled"

    # Trim to max length
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
