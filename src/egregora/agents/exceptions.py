"""Custom exceptions for the agents module."""

from egregora.exceptions import EgregoraError


class AgentError(EgregoraError):
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


class EnrichmentExecutionError(EnrichmentError):
    """Raised when enrichment execution fails."""


class MediaStagingError(EnrichmentError):
    """Raised when a media file cannot be staged for enrichment."""


class JinaFetchError(EnrichmentError):
    """Raised when Jina fetch fails."""


class EnrichmentSlugError(EnrichmentError):
    """Raised when slug generation or normalization fails."""


class EnrichmentFileError(EnrichmentError):
    """Raised when there is an issue with loading or processing an enrichment file."""


class EnrichmentParsingError(EnrichmentError):
    """Raised when parsing enrichment response fails."""
