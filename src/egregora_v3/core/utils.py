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
