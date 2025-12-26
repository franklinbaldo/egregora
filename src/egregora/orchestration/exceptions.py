"""Custom exceptions for the orchestration module."""


class OrchestrationError(Exception):
    """Base exception for orchestration errors."""


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
