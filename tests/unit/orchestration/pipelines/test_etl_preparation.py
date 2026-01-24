from datetime import date

import pytest

from egregora.orchestration.pipelines.etl.preparation import (
    validate_dates,
    validate_timezone_arg,
)


def test_validate_dates_valid():
    """Verify valid date strings are parsed correctly."""
    f, t = validate_dates("2023-01-01", "2023-12-31")
    assert f == date(2023, 1, 1)
    assert t == date(2023, 12, 31)


def test_validate_dates_none():
    """Verify None values are handled."""
    f, t = validate_dates(None, None)
    assert f is None
    assert t is None


def test_validate_dates_invalid_from():
    """Verify invalid from_date raises SystemExit."""
    with pytest.raises(SystemExit):
        validate_dates("invalid", None)


def test_validate_dates_invalid_to():
    """Verify invalid to_date raises SystemExit."""
    with pytest.raises(SystemExit):
        validate_dates(None, "invalid")


def test_validate_timezone_valid():
    """Verify valid timezone passes."""
    validate_timezone_arg("UTC")


def test_validate_timezone_invalid():
    """Verify invalid timezone raises SystemExit."""
    with pytest.raises(SystemExit):
        validate_timezone_arg("Invalid/Zone")
