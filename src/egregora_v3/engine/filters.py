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
