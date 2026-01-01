"""Custom exceptions for egregora."""


class CacheKeyNotFoundError(Exception):
    """Raised when a key is not found in the cache."""


class CacheDeserializationError(Exception):
    """Raised when a value cannot be deserialized from the cache."""


class CachePayloadTypeError(Exception):
    """Raised when the payload to be cached is of an unsupported type."""
