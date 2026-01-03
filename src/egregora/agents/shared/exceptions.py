"""Exceptions for shared agent components."""


class AgentSharedError(Exception):
    """Base class for exceptions in this module."""


class CacheError(AgentSharedError):
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
