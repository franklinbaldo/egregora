"""Exceptions for the knowledge management module."""


class ProfileError(Exception):
    """Base exception for profile-related errors."""


class ProfileNotFoundError(ProfileError):
    """Raised when a profile cannot be found."""

    def __init__(self, author_uuid: str) -> None:
        self.author_uuid = author_uuid
        super().__init__(f"Profile not found for author: {author_uuid}")


class ProfileParsingError(ProfileError):
    """Raised when a profile file cannot be parsed."""

    def __init__(self, profile_path: str, message: str) -> None:
        self.profile_path = profile_path
        super().__init__(f"Failed to parse profile at {profile_path}: {message}")


class InvalidAliasError(ProfileError):
    """Raised when an alias is invalid."""

    def __init__(self, alias: str, reason: str) -> None:
        self.alias = alias
        super().__init__(f"Invalid alias '{alias}': {reason}")
