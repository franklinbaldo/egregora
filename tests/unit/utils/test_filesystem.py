"""Unit tests for filesystem utilities."""

import pytest

from egregora.utils.exceptions import (
    FrontmatterDateFormattingError,
    MissingPostMetadataError,
)
from egregora.utils.filesystem import (
    _validate_post_metadata,
    format_frontmatter_datetime,
)


def test_validate_post_metadata_raises_for_missing_key():
    """Test that _validate_post_metadata raises MissingPostMetadataError for a missing key."""
    invalid_metadata = {"slug": "test-slug", "date": "2023-01-01"}
    with pytest.raises(MissingPostMetadataError) as excinfo:
        _validate_post_metadata(invalid_metadata)
    assert excinfo.value.missing_key == "title"


def test_format_frontmatter_datetime_raises_on_invalid_date():
    """Test that format_frontmatter_datetime raises on unparseable date."""
    with pytest.raises(FrontmatterDateFormattingError) as excinfo:
        format_frontmatter_datetime("not-a-real-date")
    assert excinfo.value.date_str == "not-a-real-date"
