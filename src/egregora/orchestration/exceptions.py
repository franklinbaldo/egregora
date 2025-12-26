"""Custom exceptions for the orchestration module."""


class OrchestrationError(Exception):
    """Base exception for orchestration errors."""


class WindowError(OrchestrationError):
    """Base exception for window processing errors."""


class WindowSizeError(WindowError):
    """Raised when a window's size exceeds the configured maximum."""


class WindowSplitError(WindowError):
    """Raised when a window cannot be split further."""


class WindowValidationError(OrchestrationError):
    """Raised when a window validation fails."""

    def __init__(self, window_index: int, reason: str) -> None:
        self.window_index = window_index
        self.reason = reason
        super().__init__(f"Window {window_index} failed validation: {reason}")


class MaxSplitDepthError(OrchestrationError):
    """Raised when the maximum split depth for a window is reached."""

    def __init__(self, window_label: str, max_depth: int) -> None:
        self.window_label = window_label
        self.max_depth = max_depth
        super().__init__(f"Max split depth of {max_depth} reached for window: {window_label}")


class OutputSinkError(OrchestrationError):
    """Raised when the output sink is not available or fails."""


class EnrichmentError(OrchestrationError):
    """Raised when an error occurs during the enrichment process."""


class MediaPersistenceError(OrchestrationError):
    """Raised when a media file fails to persist."""

    def __init__(self, media_path: str, reason: Exception) -> None:
        self.media_path = media_path
        self.reason = reason
        super().__init__(f"Failed to persist media file '{media_path}': {reason}")


class CommandProcessingError(OrchestrationError):
    """Raised when processing a command fails."""

    def __init__(self, command_text: str, reason: Exception) -> None:
        self.command_text = command_text
        self.reason = reason
        super().__init__(f"Failed to process command '{command_text}': {reason}")


class ProfileGenerationError(OrchestrationError):
    """Raised when generating profile posts fails."""


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
