"""Tests for configuration exception classes."""

from pathlib import Path
from typing import Any

import pytest

from egregora.config.exceptions import (
    ApiKeyNotFoundError,
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    InvalidDateFormatError,
    InvalidRetrievalModeError,
    InvalidTimezoneError,
    SiteNotFoundError,
)
from egregora.exceptions import EgregoraError


class TestConfigError:
    """Tests for ConfigError base exception."""

    def test_inherits_from_egregora_error(self):
        """ConfigError should inherit from EgregoraError."""
        assert issubclass(ConfigError, EgregoraError)

    def test_can_be_instantiated(self):
        """ConfigError can be created with a message."""
        error = ConfigError("Test error")
        assert str(error) == "Test error"


class TestConfigNotFoundError:
    """Tests for ConfigNotFoundError."""

    def test_stores_search_path(self):
        """Error should store the search path."""
        search_path = Path("/home/user/project")
        error = ConfigNotFoundError(search_path)
        assert error.search_path == search_path

    def test_message_includes_path(self):
        """Error message should include the search path."""
        search_path = Path("/home/user/project")
        error = ConfigNotFoundError(search_path)
        assert str(search_path) in str(error)
        assert ".egregora.toml" in str(error)

    def test_can_be_raised_and_caught(self):
        """Error can be raised and caught."""
        with pytest.raises(ConfigNotFoundError) as exc_info:
            raise ConfigNotFoundError(Path("/tmp"))
        assert exc_info.value.search_path == Path("/tmp")


class TestConfigValidationError:
    """Tests for ConfigValidationError."""

    def test_accepts_list_of_error_dicts(self):
        """Error should accept a list of error dictionaries.

        This test verifies the fix for the type annotation bug where
        dict[str, any] should be dict[str, Any].
        """
        errors: list[dict[str, Any]] = [
            {"field": "name", "error": "Required field missing"},
            {"field": "age", "error": "Must be positive", "value": -1},
        ]
        error = ConfigValidationError(errors)
        assert error.errors == errors

    def test_accepts_none_for_errors(self):
        """Error should accept None and default to empty list."""
        error = ConfigValidationError(None)
        assert error.errors == []

    def test_defaults_to_empty_list(self):
        """Error should default to empty list when no argument provided."""
        error = ConfigValidationError()
        assert error.errors == []

    def test_message_includes_error_count(self):
        """Error message should include the number of errors."""
        errors = [
            {"field": "name", "error": "Required"},
            {"field": "age", "error": "Invalid"},
        ]
        error = ConfigValidationError(errors)
        assert "2 error(s)" in str(error)

    def test_error_dict_values_can_be_any_type(self):
        """Error dict values can be any type (str, int, list, etc.).

        This specifically tests that the Any type annotation works correctly.
        """
        errors: list[dict[str, Any]] = [
            {"field": "name", "message": "Error", "code": 123},
            {"field": "tags", "values": ["tag1", "tag2"], "nested": {"a": 1}},
            {"field": "flag", "enabled": True},
        ]
        error = ConfigValidationError(errors)
        assert len(error.errors) == 3
        assert error.errors[0]["code"] == 123
        assert error.errors[1]["values"] == ["tag1", "tag2"]
        assert error.errors[2]["enabled"] is True


class TestSiteNotFoundError:
    """Tests for SiteNotFoundError."""

    def test_stores_site_name_and_available_sites(self):
        """Error should store the site name and available sites."""
        error = SiteNotFoundError("prod", ["dev", "staging"])
        assert error.site_name == "prod"
        assert error.available_sites == ["dev", "staging"]

    def test_message_includes_site_info(self):
        """Error message should include site name and available sites."""
        error = SiteNotFoundError("prod", ["dev", "staging"])
        message = str(error)
        assert "prod" in message
        assert "dev" in message
        assert "staging" in message


class TestInvalidDateFormatError:
    """Tests for InvalidDateFormatError."""

    def test_stores_date_string(self):
        """Error should store the invalid date string."""
        error = InvalidDateFormatError("2023-13-45")
        assert error.date_string == "2023-13-45"

    def test_message_includes_date_and_format(self):
        """Error message should include the date and expected format."""
        error = InvalidDateFormatError("2023-13-45")
        message = str(error)
        assert "2023-13-45" in message
        assert "YYYY-MM-DD" in message


class TestApiKeyNotFoundError:
    """Tests for ApiKeyNotFoundError."""

    def test_stores_env_var_name(self):
        """Error should store the environment variable name."""
        error = ApiKeyNotFoundError("GOOGLE_API_KEY")
        assert error.env_var == "GOOGLE_API_KEY"

    def test_message_includes_env_var(self):
        """Error message should include the environment variable."""
        error = ApiKeyNotFoundError("GOOGLE_API_KEY")
        assert "GOOGLE_API_KEY" in str(error)


class TestInvalidTimezoneError:
    """Tests for InvalidTimezoneError."""

    def test_stores_timezone_and_exception(self):
        """Error should store the timezone string and original exception."""
        original = ValueError("Unknown timezone")
        error = InvalidTimezoneError("Invalid/Timezone", original)
        assert error.timezone_str == "Invalid/Timezone"
        assert error.original_exception is original

    def test_message_includes_timezone_and_reason(self):
        """Error message should include timezone and original error."""
        original = ValueError("Unknown timezone")
        error = InvalidTimezoneError("Invalid/Timezone", original)
        message = str(error)
        assert "Invalid/Timezone" in message
        assert "Unknown timezone" in message


class TestInvalidRetrievalModeError:
    """Tests for InvalidRetrievalModeError."""

    def test_stores_mode(self):
        """Error should store the invalid mode."""
        error = InvalidRetrievalModeError("invalid")
        assert error.mode == "invalid"

    def test_message_includes_mode_and_valid_options(self):
        """Error message should include the mode and valid options."""
        error = InvalidRetrievalModeError("invalid")
        message = str(error)
        assert "invalid" in message
        assert "ann" in message
        assert "exact" in message
