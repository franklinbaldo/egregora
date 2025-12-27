"""Custom exceptions for the WhatsApp adapter."""


class WhatsAppAdapterError(Exception):
    """Base exception for all WhatsApp adapter errors."""


class WhatsAppParsingError(WhatsAppAdapterError):
    """Base exception for all WhatsApp parsing errors."""


class WhatsAppParsingIOError(WhatsAppParsingError):
    """Raised for I/O-related errors during parsing, like file not found or decoding errors."""


class DateParsingError(WhatsAppParsingError):
    """Raised when a date string cannot be parsed."""

    def __init__(self, date_str: str, message: str | None = None) -> None:
        self.date_str = date_str
        if message is None:
            message = f"Failed to parse date string: '{self.date_str}'"
        super().__init__(message)


class TimeParsingError(WhatsAppParsingError):
    """Raised when a time string cannot be parsed."""

    def __init__(self, time_str: str, message: str | None = None) -> None:
        self.time_str = time_str
        if message is None:
            message = f"Failed to parse time string: '{self.time_str}'"
        super().__init__(message)


class EmptyChatLogError(WhatsAppParsingError):
    """Raised when the WhatsApp chat log file is empty."""

    def __init__(self, path: str, message: str | None = None) -> None:
        self.path = path
        if message is None:
            message = f"Chat log file is empty: '{self.path}'"
        super().__init__(message)


class NoMessagesFoundError(WhatsAppParsingError):
    """Raised when no messages are found in the source."""

    def __init__(self, source_name: str) -> None:
        """Initialize the exception."""
        self.source_name = source_name
        message = f"No messages found in '{source_name}'"
        super().__init__(message)


class InvalidZipFileError(WhatsAppParsingError):
    """Raised when the ZIP file is corrupted or not a valid ZIP archive."""

    def __init__(self, zip_path: str, message: str | None = None) -> None:
        """Initialize the exception."""
        self.zip_path = zip_path
        if message is None:
            message = f"Invalid or corrupted ZIP file at '{zip_path}'"
        super().__init__(message)


class MalformedLineError(WhatsAppParsingError):
    """Raised when a line in the chat log does not conform to the expected format."""

    def __init__(self, line: str, original_error: Exception, line_number: int | None = None) -> None:
        """Initialize the exception."""
        self.line = line
        self.original_error = original_error
        self.line_number = line_number

        message = "Malformed line encountered"
        if line_number:
            message += f" at line {line_number}"
        message += f": '{line}'. Reason: {original_error}"
        super().__init__(message)


class ChatFileNotFoundError(WhatsAppParsingError):
    """Raised when the chat .txt file cannot be found in the ZIP archive."""

    def __init__(self, zip_path: str) -> None:
        """Initialize the exception."""
        self.zip_path = zip_path
        message = f"No WhatsApp chat file found in {zip_path}"
        super().__init__(message)


# Media Delivery Errors
class MediaDeliveryError(WhatsAppParsingError):
    """Base exception for errors related to media file delivery."""


class InvalidMediaReferenceError(MediaDeliveryError):
    """Raised for suspicious or invalid media references (e.g., path traversal)."""

    def __init__(self, media_reference: str) -> None:
        self.media_reference = media_reference
        message = f"Invalid media reference provided: '{media_reference}'"
        super().__init__(message)


class MissingZipPathError(MediaDeliveryError):
    """Raised when the zip_path keyword argument is missing."""

    def __init__(self) -> None:
        message = "'zip_path' keyword argument is required but was not provided."
        super().__init__(message)


class ZipPathNotFoundError(MediaDeliveryError):
    """Raised when the provided ZIP file path does not exist."""

    def __init__(self, zip_path: str) -> None:
        self.zip_path = zip_path
        message = f"ZIP file not found at the provided path: '{zip_path}'"
        super().__init__(message)


class MediaNotFoundError(MediaDeliveryError):
    """Raised when the specified media file is not found within the ZIP archive."""

    def __init__(self, media_reference: str, zip_path: str) -> None:
        self.media_reference = media_reference
        self.zip_path = zip_path
        message = f"Media file '{media_reference}' not found in '{zip_path}'."
        super().__init__(message)


class MediaExtractionError(MediaDeliveryError):
    """Raised for general errors during media extraction from the ZIP file."""

    def __init__(self, media_reference: str, zip_path: str, original_error: Exception) -> None:
        self.media_reference = media_reference
        self.zip_path = zip_path
        self.original_error = original_error
        message = f"Failed to extract '{media_reference}' from '{zip_path}'. Reason: {original_error}"
        super().__init__(message)


class ChatEncodingError(WhatsAppParsingError):
    """Raised when the chat file cannot be decoded."""

    def __init__(self, filename: str, original_error: UnicodeDecodeError) -> None:
        """Initialize the exception."""
        self.filename = filename
        self.original_error = original_error
        message = f"Failed to decode chat file '{filename}' due to encoding issue: {original_error}"
        super().__init__(message)
