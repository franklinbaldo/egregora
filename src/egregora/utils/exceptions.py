"""Custom exceptions for filesystem operations."""


class FilesystemError(Exception):
    """Base exception for filesystem-related errors."""


class MissingMetadataError(FilesystemError):
    """Raised when required metadata for a post is missing."""

    def __init__(self, missing_keys: list[str]) -> None:
        self.missing_keys = missing_keys
        message = f"Missing required metadata keys: {', '.join(missing_keys)}"
        super().__init__(message)


class UniqueFilenameError(FilesystemError):
    """Raised when a unique filename cannot be generated after a set number of attempts."""

    def __init__(self, base_slug: str, attempts: int) -> None:
        self.base_slug = base_slug
        self.attempts = attempts
        message = f"Could not generate a unique filename for slug '{base_slug}' after {attempts} attempts."
        super().__init__(message)


class MissingPostMetadataError(FilesystemError):
    """Raised when required post metadata is missing."""

    def __init__(self, missing_key: str) -> None:
        self.missing_key = missing_key
        super().__init__(f"Missing required metadata key: '{self.missing_key}'")


class FrontmatterDateFormattingError(FilesystemError):
    """Raised when a date string for frontmatter cannot be parsed."""

    def __init__(self, date_str: str, original_exception: Exception) -> None:
        self.date_str = date_str
        self.original_exception = original_exception
        super().__init__(
            f"Failed to parse date string for frontmatter: '{self.date_str}'. "
            f"Original error: {original_exception}"
        )


class DateTimeUtilsError(Exception):
    """Base exception for datetime utility errors."""


class DateTimeParsingError(DateTimeUtilsError):
    """Raised when a date/time string cannot be parsed."""

    def __init__(self, value: str, original_exception: Exception | None = None) -> None:
        self.value = value
        self.original_exception = original_exception
        message = f"Failed to parse date/time string: '{self.value}'"
        if original_exception:
            message += f". Original error: {original_exception}"
        super().__init__(message)
