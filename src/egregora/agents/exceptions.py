"""Custom exceptions for the agents module."""


class AgentError(Exception):
    """Base exception for all agent-related errors."""


class EnrichmentError(AgentError):
    """Base exception for errors during the enrichment process."""


class MediaStagingError(EnrichmentError):
    """Raised when a media file cannot be staged for enrichment."""


class BannerError(AgentError):
    """Base exception for errors during banner generation."""


class BannerTaskDataError(BannerError):
    """Raised when banner task data is invalid or missing."""


class BannerTaskPayloadError(BannerError):
    """Raised when banner task payload is malformed."""


class JournalError(AgentError):
    """Base exception for errors during journal writing."""


class JournalFileSystemError(JournalError):
    """Raised when journal file operations fail."""


class JournalTemplateError(JournalError):
    """Raised when journal template rendering fails."""
