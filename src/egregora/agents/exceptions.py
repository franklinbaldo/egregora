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


class JournalError(AgentError):
    """Base exception for errors during journal operations."""


class JournalTemplateError(JournalError):
    """Raised when a journal template cannot be loaded or rendered."""


class JournalFileSystemError(JournalError):
    """Raised when a journal file cannot be written to the filesystem."""
