"""Custom exceptions for egregora."""


class EgregoraError(Exception):
    """Base class for exceptions in this module."""


class CacheKeyNotFoundError(EgregoraError):
    """Raised when a cache key is not found."""

    def __init__(self, key: str) -> None:
        self.key = key
        message = f"Key not found in cache: '{key}'"
        super().__init__(message)


