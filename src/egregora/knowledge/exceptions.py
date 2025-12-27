"""Exceptions for the knowledge management module."""


class ProfileError(Exception):
    """Base exception for profile-related errors."""


class ProfileNotFoundError(ProfileError):
    """Raised when a profile cannot be found."""

    def __init__(self, message: str, *, author_uuid: str | None = None, path: str | None = None) -> None:
        super().__init__(message)
        self.author_uuid = author_uuid
        self.path = path


class ProfileParseError(ProfileError):
    """Raised when a profile file cannot be parsed."""

    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


# Alias for backward compatibility
ProfileParsingError = ProfileParseError


class InvalidAliasError(ProfileError):
    """Raised when a profile alias is invalid."""

    def __init__(self, message: str, *, alias: str | None = None) -> None:
        super().__init__(message)
        self.alias = alias
