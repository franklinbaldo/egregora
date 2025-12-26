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
