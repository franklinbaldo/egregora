"""Custom exceptions for the agents module."""


class AgentError(Exception):
    """Base exception for all agent-related errors."""


class BannerError(AgentError):
    """Base exception for errors during banner generation."""


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


class EnrichmentError(AgentError):
    """Base exception for errors during the enrichment process."""


class MediaStagingError(EnrichmentError):
    """Raised when a media file cannot be staged for enrichment."""


class JournalTemplateError(AgentError):
    """Raised on errors related to journal template loading or rendering."""


class JournalFileSystemError(AgentError):
    """Raised on file system errors during journal creation."""
