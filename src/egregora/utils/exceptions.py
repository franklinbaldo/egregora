"""Custom exceptions for egregora."""


class CacheKeyNotFoundError(Exception):
    """Raised when a key is not found in the cache."""


class CacheDeserializationError(Exception):
    """Raised when a cached value cannot be deserialized."""


class CachePayloadTypeError(Exception):
    """Raised when the payload to be cached is of an unexpected type."""
