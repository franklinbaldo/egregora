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


class FilesystemOperationError(FilesystemError):
    """Base exception for file I/O errors."""

    def __init__(self, path: str, original_exception: Exception, message: str | None = None) -> None:
        self.path = path
        self.original_exception = original_exception
        if message is None:
            message = f"An error occurred at path: {self.path}. Original error: {original_exception}"
        super().__init__(message)


class DirectoryCreationError(FilesystemOperationError):
    """Raised when creating a directory fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to create directory at: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class FileWriteError(FilesystemOperationError):
    """Raised when writing a file fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to write file to: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class DateExtractionError(FilesystemError):
    """Raised when a date cannot be extracted from a string."""

    def __init__(self, date_str: str) -> None:
        self.date_str = date_str
        message = f"Could not extract a valid date from '{self.date_str}'"
        super().__init__(message)


class CacheError(Exception):
    """Base exception for cache-related errors."""


class CacheDeserializationError(CacheError):
    """Raised when a cache entry cannot be deserialized."""

    def __init__(self, key: str, original_exception: Exception) -> None:
        self.key = key
        self.original_exception = original_exception
        message = f"Failed to deserialize cache entry for key '{key}'. Original error: {original_exception}"
        super().__init__(message)


class CachePayloadTypeError(CacheError):
    """Raised when a cache entry has an unexpected type."""

    def __init__(self, key: str, payload_type: type) -> None:
        self.key = key
        self.payload_type = payload_type
        message = (
            f"Unexpected cache payload type for key '{key}': got {payload_type.__name__}, expected dict."
        )
        super().__init__(message)


class CacheKeyNotFoundError(CacheError):
    """Raised when a key is not found in the cache."""

    def __init__(self, key: str) -> None:
        self.key = key
        message = f"Key not found in cache: '{key}'"
        super().__init__(message)


class AuthorsError(Exception):
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


class DateTimeError(Exception):
    """Base exception for datetime parsing and manipulation errors."""


class InvalidDateTimeInputError(DateTimeError):
    """Raised when the input value for a datetime operation is invalid (e.g., None, empty string)."""

    def __init__(self, value: str, reason: str) -> None:
        self.value = value
        self.reason = reason
        super().__init__(f"Invalid datetime input '{value}': {reason}")


class DateTimeParsingError(DateTimeError):
    """Raised when a string cannot be parsed into a datetime object."""

    def __init__(self, value: str, original_exception: Exception) -> None:
        self.value = value
        self.original_exception = original_exception
        super().__init__(f"Failed to parse datetime from '{value}': {original_exception}")
