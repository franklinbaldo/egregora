"""Custom exceptions for filesystem utilities."""


class FilesystemOperationError(Exception):
    """Base exception for filesystem operations."""


class MissingPostMetadataError(FilesystemOperationError):
    """Raised when required post metadata is missing."""

    def __init__(self, missing_key: str):
        self.missing_key = missing_key
        super().__init__(f"Missing required metadata key: '{self.missing_key}'")


class FrontmatterDateFormattingError(FilesystemOperationError):
    """Raised when a date string for frontmatter cannot be parsed."""

    def __init__(self, date_str: str, original_exception: Exception):
        self.date_str = date_str
        self.original_exception = original_exception
        super().__init__(
            f"Failed to parse date string for frontmatter: '{self.date_str}'. "
            f"Original error: {original_exception}"
        )
