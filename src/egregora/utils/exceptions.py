"""Custom exceptions for egregora."""


class CacheKeyNotFoundError(Exception):
    """Raised when a cache key is not found."""


class CacheDeserializationError(Exception):
    """Raised when a cache key is not found."""


class CachePayloadTypeError(Exception):
    """Raised when a cache key is not found."""
