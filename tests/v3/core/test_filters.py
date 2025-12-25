from datetime import UTC, datetime

import pytest

from src.egregora_v3.core.filters import format_datetime, normalize_content_type


@pytest.mark.parametrize(
    ("dt", "expected"),
    [
        (datetime(2023, 1, 1, 12, 30, 0, tzinfo=UTC), "2023-01-01T12:30:00Z"),
        (datetime(2023, 1, 1, 12, 30, 0), "2023-01-01T12:30:00Z"),
    ],
)
def test_format_datetime(dt, expected):
    """Test RFC 3339 formatting for datetime objects."""
    assert format_datetime(dt) == expected


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("text/markdown", "text"),
        ("text/html", "html"),
        (None, "text"),
        ("application/json", "application/json"),
        ("", "text"),
    ],
)
def test_normalize_content_type(content_type, expected):
    """Test normalization of content types for Atom feed."""
    assert normalize_content_type(content_type) == expected
