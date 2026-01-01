"""Text manipulation utilities."""

from pymdownx.slugs import slugify as _slugify

# Pre-configure slugifiers for efficiency, matching legacy behavior.
_slugify_lower = _slugify(case="lower", separator="-")
_slugify_case = _slugify(separator="-")  # Default case is 'preserve'


def slugify(text: str, *, lowercase: bool = True) -> str:
    """Converts text to a URL-friendly slug.

    This is a simplified wrapper around `pymdownx.slugs.slugify`
    and uses its default behavior as much as possible.

    Args:
        text: The text to convert.
        lowercase: Whether to convert the slug to lowercase. Defaults to True.

    Returns:
        The slugified string. Returns an empty string if the input is None.

    """
    if text is None:
        return ""

    slugifier = _slugify_lower if lowercase else _slugify_case
    return slugifier(text, sep="-")
