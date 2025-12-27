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


class MissingMetadataError(InvalidFrontmatterError):
    """Raised when required metadata is missing."""


class UniqueFilenameError(UtilsError):
    """Raised when a unique filename cannot be generated."""
