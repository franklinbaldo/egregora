"""Exceptions for the knowledge management module."""
from egregora.exceptions import EgregoraError


class ProfileError(EgregoraError):
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


class InvalidAliasError(ProfileError):
    """Raised when a profile alias is invalid."""

    def __init__(self, message: str, *, alias: str | None = None) -> None:
        super().__init__(message)
        self.alias = alias


class AuthorsError(ProfileError):
    """Base exception for author management errors."""


class AuthorsFileError(AuthorsError):
    """Base exception for errors related to the .authors.yml file."""

    def __init__(
        self, path: str, original_exception: Exception | None = None, message: str | None = None
    ) -> None:
        self.path = path
        self.original_exception = original_exception
        if message is None:
            message = f"An error occurred involving authors file at: {path}"
        super().__init__(message)


class AuthorsFileLoadError(AuthorsFileError):
    """Raised when the .authors.yml file cannot be read from the filesystem."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to load authors file from path: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class AuthorsFileParseError(AuthorsFileError):
    """Raised when the .authors.yml file is malformed and cannot be parsed."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to parse YAML from authors file: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class AuthorsFileSaveError(AuthorsFileError):
    """Raised when the .authors.yml file cannot be written to the filesystem."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to save authors file to path: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class AuthorExtractionError(AuthorsError):
    """Raised when author information cannot be extracted from a post."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        self.path = path
        self.original_exception = original_exception
        super().__init__(
            f"Failed to extract author(s) from post: {self.path}. Original error: {original_exception}"
        )
