"""Exceptions for the utils package."""

from __future__ import annotations


class UtilsError(Exception):
    """Base class for exceptions in this module."""


class AuthorsFileError(UtilsError):
    """Base class for errors related to the .authors.yml file."""


class AuthorsFileParseError(AuthorsFileError):
    """Raised when the .authors.yml file cannot be parsed."""


class AuthorsFileIOError(AuthorsFileError):
    """Raised when there is an error reading or writing the .authors.yml file."""


class PostParseError(UtilsError):
    """Raised when a post file cannot be parsed."""


class PathResolutionError(UtilsError):
    """Raised when a path cannot be resolved."""


class InvalidFrontmatterError(UtilsError):
    """Raised for invalid frontmatter."""


class FrontmatterDateFormattingError(InvalidFrontmatterError):
    """Raised for date formatting errors in frontmatter."""

    def __init__(self, date_str: str, original_exception: Exception) -> None:
        self.date_str = date_str
        self.original_exception = original_exception
        super().__init__(
            f"Failed to parse date string for frontmatter: '{self.date_str}'. "
            f"Original error: {original_exception}"
        )


class MissingMetadataError(InvalidFrontmatterError):
    """Raised when required metadata is missing."""

    def __init__(self, missing_keys: list[str]) -> None:
        self.missing_keys = missing_keys
        message = f"Missing required metadata keys: {', '.join(missing_keys)}"
        super().__init__(message)


class UniqueFilenameError(UtilsError):
    """Raised when a unique filename cannot be generated."""

    def __init__(self, base_slug: str, attempts: int) -> None:
        self.base_slug = base_slug
        self.attempts = attempts
        message = f"Could not generate a unique filename for slug '{base_slug}' after {attempts} attempts."
        super().__init__(message)


class ModelError(UtilsError):
    """Base class for model-related errors."""


class ModelFallbackError(ModelError):
    """Raised during model fallback operations."""


class OpenRouterAPIError(ModelError):
    """Raised when the OpenRouter API call fails."""


class ModelConfigurationError(ModelError):
    """Raised for model configuration errors."""
