"""Custom exceptions for the banner agent."""

from egregora.agents.exceptions import AgentError


class BannerError(AgentError):
    """Base exception for errors during banner generation."""


class BannerConfigurationError(BannerError):
    """Raised when banner generation is not configured correctly (e.g. missing API key)."""


class BannerGenerationError(BannerError):
    """Raised when the underlying generation provider fails."""


class BannerNoImageError(BannerGenerationError):
    """Raised when the provider returns a success response but no image data."""


class BannerTaskPayloadError(BannerError):
    """Raised when a banner task has a malformed or missing payload."""

    def __init__(self, task_id: str, message: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task {task_id}: {message}")


class BannerTaskDataError(BannerError):
    """Raised when a banner task payload is missing required data."""

    def __init__(self, task_id: str, missing_fields: list[str]) -> None:
        self.task_id = task_id
        self.missing_fields = missing_fields
        fields = ", ".join(missing_fields)
        super().__init__(f"Task {task_id}: Missing required fields: {fields}")
