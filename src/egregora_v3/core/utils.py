"""V3 utility functions - independent of V2."""

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

    if overlap >= max_chars:
        overlap = max_chars // 2

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end > len(text):
            end = len(text)

        chunk = text[start:end]

        if end < len(text):
            # Find the last space to avoid cutting words
            last_space = chunk.rfind(" ")
            if last_space != -1:
                end = start + last_space
                chunk = text[start:end]

        chunks.append(chunk)

        start = end - overlap
        if start >= len(text):
            break

        # Find the first space to avoid starting mid-word
        first_space = text.find(" ", start)
        if first_space != -1:
            start = first_space + 1

    return chunks
