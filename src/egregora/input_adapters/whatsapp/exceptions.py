"""Exceptions for the WhatsApp input adapter."""


class WhatsAppError(Exception):
    """Base exception for WhatsApp adapter errors."""


class WhatsAppAdapterError(WhatsAppError):
    """Base exception for adapter-level errors."""


class InvalidZipFileError(WhatsAppAdapterError):
    """Raised when the input file is not a valid ZIP file."""


class MissingZipPathError(WhatsAppAdapterError):
    """Raised when the zip_path is not provided for media delivery."""


class ZipPathNotFoundError(WhatsAppAdapterError):
    """Raised when the provided zip_path does not exist."""


class InvalidMediaReferenceError(WhatsAppAdapterError):
    """Raised when a media reference is invalid (e.g., path traversal)."""


class MediaNotFoundError(WhatsAppAdapterError):
    """Raised when a media reference is not found in the ZIP."""

    def __init__(self, zip_path: str, media_reference: str) -> None:
        self.zip_path = zip_path
        self.media_reference = media_reference
        super().__init__(f"Media '{media_reference}' not found in '{zip_path}'")


class MediaExtractionError(WhatsAppAdapterError):
    """Raised when media cannot be extracted from the ZIP file."""

    def __init__(self, media_reference: str, zip_path: str, reason: str) -> None:
        self.media_reference = media_reference
        self.zip_path = zip_path
        self.reason = reason
        super().__init__(f"Failed to extract '{media_reference}' from '{zip_path}': {reason}")


class WhatsAppParsingError(WhatsAppError):
    """Base exception for parsing errors."""


class ChatFileNotFoundError(WhatsAppParsingError):
    """Raised when the chat file cannot be found in the ZIP archive."""

    def __init__(self, zip_path: str) -> None:
        self.zip_path = zip_path
        super().__init__(f"No WhatsApp chat file found in {zip_path}")


class DateParsingError(WhatsAppParsingError):
    """Raised when a date string cannot be parsed."""


class TimeParsingError(WhatsAppParsingError):
    """Raised when a time string cannot be parsed."""


class MalformedLineError(WhatsAppParsingError):
    """Raised when a line in the chat log is malformed."""

    def __init__(self, line: str, original_error: Exception) -> None:
        self.line = line
        self.original_error = original_error
        super().__init__(f"Malformed line encountered: '{line}'. Original error: {original_error}")


class NoMessagesFoundError(WhatsAppParsingError):
    """Raised when no messages are found after parsing."""
