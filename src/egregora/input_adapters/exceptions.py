"""Exceptions for input adapters."""

class AdapterError(Exception):
    """Base exception for all adapter errors."""


class UnknownAdapterError(AdapterError, LookupError):
    """Raised when an adapter cannot be found."""

    def __init__(self, identifier: str, available: list[str] | None = None) -> None:
        self.identifier = identifier
        self.available = available or []
        msg = f"Unknown adapter source: '{identifier}'"
        if self.available:
            msg += f". Available: {', '.join(self.available)}"
        super().__init__(msg)


class AdapterLoadError(AdapterError):
    """Raised when an adapter fails to load (plugin or built-in)."""
    def __init__(self, name: str, reason: str | Exception) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Failed to load adapter '{name}': {reason}")
