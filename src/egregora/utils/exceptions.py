"""Custom exceptions for egregora."""


class CacheKeyNotFoundError(Exception):
    """Raised when a key is not found in the cache."""

    def __init__(self, key: str) -> None:
        self.key = key
        message = f"Key not found in cache: '{key}'"
        super().__init__(message)


class CacheDeserializationError(Exception):
    """Raised when a cached value cannot be deserialized."""

    def __init__(self, key: str, original_exception: Exception) -> None:
        self.key = key
        self.original_exception = original_exception
        message = f"Failed to deserialize cache entry for key '{key}'. Original error: {original_exception}"
        super().__init__(message)


class CachePayloadTypeError(Exception):
    """Raised when the payload to be cached is of an unexpected type."""

    def __init__(self, key: str, payload_type: type) -> None:
        self.key = key
        self.payload_type = payload_type
        message = (
            f"Unexpected cache payload type for key '{key}': got {payload_type.__name__}, expected dict."
        )
        super().__init__(message)
