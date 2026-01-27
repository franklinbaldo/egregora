"""Exceptions for the orchestration module."""

from egregora.exceptions import EgregoraError


class OrchestrationError(EgregoraError):
    """Base exception for orchestration errors."""


class WindowError(OrchestrationError):
    """Base exception for window processing errors."""


class WindowSizeError(WindowError):
    """Raised when a window's size exceeds the configured maximum."""


class WindowSplitError(WindowError):
    """Raised when a window cannot be split further."""


class OutputSinkError(OrchestrationError):
    """Raised when the output sink is not properly configured or fails."""


class EnrichmentError(OrchestrationError):
    """Raised when an error occurs during the enrichment process."""


class MediaPersistenceError(OrchestrationError):
    """Raised when media files fail to be persisted."""


class CommandProcessingError(OrchestrationError):
    """Raised when an error occurs while processing a command."""


class CommandAnnouncementError(CommandProcessingError):
    """Raised when a command cannot be converted to an announcement."""


class ProfileGenerationError(OrchestrationError):
    """Raised when an error occurs during profile generation."""


class PipelineSetupError(OrchestrationError):
    """Base exception for errors during pipeline setup."""


class ApiKeyMissingError(PipelineSetupError):
    """Raised when the Gemini API key is not found."""


class ApiKeyInvalidError(PipelineSetupError):
    """Raised when the Gemini API key is invalid."""

    def __init__(self, message: str, validation_errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.validation_errors = validation_errors or []


class SourceNotFoundError(PipelineSetupError):
    """Raised when a requested source is not found in the configuration."""


class SiteNotInitializedError(PipelineSetupError):
    """Raised when the site directory is not properly initialized (e.g., missing mkdocs.yml)."""


class InvalidDateArgumentError(PipelineSetupError):
    """Raised when a date argument has an invalid format."""


class InvalidTimezoneArgumentError(PipelineSetupError):
    """Raised when a timezone argument is invalid."""


class ConfigError(PipelineSetupError):
    """Base class for configuration-related errors."""


class ConfigNotFoundError(ConfigError):
    """Raised when .egregora.toml is not found."""


class ConfigValidationError(ConfigError):
    """Raised on Pydantic validation error during config load."""

    def __init__(self, message: str, exc: Exception | None = None) -> None:
        super().__init__(message)
        self.original_exception = exc


class CacheError(OrchestrationError):
    """Base exception for cache-related errors."""


class CacheKeyNotFoundError(CacheError):
    """Raised when a cache key is not found."""

    def __init__(self, key: str) -> None:
        self.key = key
        message = f"Key not found in cache: '{key}'"
        super().__init__(message)


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
