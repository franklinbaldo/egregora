"""Custom exceptions for configuration handling."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from egregora.exceptions import EgregoraError


class ConfigError(EgregoraError):
    """Base exception for all configuration-related errors."""


class ConfigNotFoundError(ConfigError):
    """Raised when the configuration file cannot be found."""

    def __init__(self, search_path: Path) -> None:
        self.search_path = search_path
        super().__init__(f"Could not find .egregora.toml in or above {search_path}")


class ConfigValidationError(ConfigError):
    """Raised when the configuration file fails validation."""

    def __init__(self, errors: Sequence[dict[str, Any]] | None = None) -> None:
        self.errors = errors or []
        super().__init__(f"Configuration validation failed with {len(self.errors)} error(s).")


class SiteNotFoundError(ConfigError):
    """Raised when a specified site is not found in the configuration."""

    def __init__(self, site_name: str, available_sites: list[str]) -> None:
        self.site_name = site_name
        self.available_sites = available_sites
        super().__init__(f"Site '{site_name}' not found. Available sites: {', '.join(available_sites)}")


class InvalidDateFormatError(ConfigError):
    """Raised when a date string is in an invalid format."""

    def __init__(self, date_string: str) -> None:
        self.date_string = date_string
        super().__init__(f"Invalid date format: '{date_string}'. Expected YYYY-MM-DD.")


class ApiKeyNotFoundError(ConfigError):
    """Raised when a required API key is not found in environment variables."""

    def __init__(self, env_var: str) -> None:
        self.env_var = env_var
        super().__init__(f"API key environment variable not set: {env_var}")


class InvalidTimezoneError(ConfigError):
    """Raised when a timezone string is invalid."""

    def __init__(self, timezone_str: str, original_exception: Exception) -> None:
        self.timezone_str = timezone_str
        self.original_exception = original_exception
        super().__init__(f"Invalid timezone '{timezone_str}': {original_exception}")


class InvalidRetrievalModeError(ConfigError):
    """Raised when an invalid retrieval mode is specified."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        super().__init__(f"Invalid retrieval mode: '{mode}'. Choose 'ann' or 'exact'.")


class InvalidConfigurationValueError(ConfigError):
    """Raised when a configuration value is invalid."""


class InvalidEnrichmentConfigError(InvalidConfigurationValueError):
    """Raised when enrichment configuration is invalid."""


class SiteStructureError(ConfigError):
    """Raised when required site directory structure is missing."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Invalid site structure at '{path}': {reason}")


class InvalidDatabaseUriError(ConfigError):
    """Raised when a database connection URI is malformed."""

    def __init__(self, uri: str, reason: str) -> None:
        self.uri = uri
        self.reason = reason
        super().__init__(f"Invalid database URI '{uri}': {reason}")
