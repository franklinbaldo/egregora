import pytest
from datetime import date, datetime, timezone
from egregora.output_adapters.mkdocs.markdown_utils import (
    extract_clean_date,
    format_frontmatter_datetime,
    DateExtractionError,
    FrontmatterDateFormattingError,
)

class TestExtractCleanDate:
    def test_extract_from_datetime(self):
        dt = datetime(2023, 1, 15, 10, 30, tzinfo=timezone.utc)
        assert extract_clean_date(dt) == "2023-01-15"

    def test_extract_from_date(self):
        d = date(2023, 1, 15)
        assert extract_clean_date(d) == "2023-01-15"

    def test_extract_from_string_iso(self):
        assert extract_clean_date("2023-01-15") == "2023-01-15"

    def test_extract_from_string_with_text(self):
        assert extract_clean_date("Date: 2023-01-15") == "2023-01-15"
        assert extract_clean_date("Backup from 2023-01-15 10:00") == "2023-01-15"

    def test_extract_failure_no_date(self):
        with pytest.raises(DateExtractionError):
            extract_clean_date("No date here")

    def test_extract_failure_invalid_date(self):
        # Regex matches 2023-99-99 but parser should reject it
        with pytest.raises(DateExtractionError):
            extract_clean_date("2023-99-99")

class TestFormatFrontmatterDatetime:
    def test_format_datetime(self):
        dt = datetime(2023, 1, 15, 10, 30, tzinfo=timezone.utc)
        # Should return "YYYY-MM-DD HH:MM"
        assert format_frontmatter_datetime(dt) == "2023-01-15 10:30"

    def test_format_date(self):
        d = date(2023, 1, 15)
        # Defaults to 00:00
        assert format_frontmatter_datetime(d) == "2023-01-15 00:00"

    def test_format_string_iso(self):
        assert format_frontmatter_datetime("2023-01-15T10:30:00Z") == "2023-01-15 10:30"

    def test_format_string_flexible(self):
        assert format_frontmatter_datetime("2023-01-15 10:30") == "2023-01-15 10:30"

    def test_format_failure(self):
        with pytest.raises(FrontmatterDateFormattingError):
            format_frontmatter_datetime("Invalid Date")
