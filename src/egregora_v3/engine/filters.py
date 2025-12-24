"""Custom Jinja2 filters for V3 agents."""

from datetime import datetime


def format_datetime(value: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime object.

    Args:
        value: Datetime to format
        format_str: strftime format string

    Returns:
        Formatted datetime string

    """
    if not isinstance(value, datetime):
        return str(value)
    return value.strftime(format_str)


def isoformat(value: datetime) -> str:
    """Format datetime as ISO 8601.

    Args:
        value: Datetime to format

    Returns:
        ISO 8601 formatted string

    """
    if not isinstance(value, datetime):
        return str(value)
    return value.isoformat()


def truncate_words(value: str, num_words: int = 50, suffix: str = "...") -> str:
    """Truncate string to specified number of words.

    Args:
        value: String to truncate
        num_words: Maximum number of words
        suffix: Suffix to add if truncated

    Returns:
        Truncated string

    """
    words = value.split()
    if len(words) <= num_words:
        return value

    truncated = " ".join(words[:num_words])
    return f"{truncated}{suffix}"
