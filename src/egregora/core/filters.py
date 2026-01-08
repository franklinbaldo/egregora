from datetime import UTC, datetime


def format_datetime(dt: datetime) -> str:
    """Format datetime as RFC 3339 (Atom requirement)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_content_type(content_type: str | None) -> str:
    """Normalize content type for Atom."""
    if content_type == "text/markdown":
        return "text"
    if content_type == "text/html":
        return "html"
    return content_type or "text"
