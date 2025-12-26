"""Custom exceptions for the WhatsApp parser."""


class WhatsAppParsingError(Exception):
    """Base exception for all WhatsApp parsing errors."""


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
