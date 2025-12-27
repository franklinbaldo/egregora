"""Exceptions for the orchestration module."""


class OrchestrationError(Exception):
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


class CommandProcessingError(OrchestrationError):
    """Raised when an error occurs while processing a command."""


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
