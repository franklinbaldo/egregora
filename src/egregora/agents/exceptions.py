"""Custom exceptions for the agents module."""


class AgentError(Exception):
    """Base exception for all agent-related errors."""


class EnrichmentError(AgentError):
    """Base exception for errors during the enrichment process."""


class MediaStagingError(EnrichmentError):
    """Raised when a media file cannot be staged for enrichment."""


class JournalError(AgentError):
    """Base exception for journal-related errors."""


class JournalTemplateError(JournalError):
    """Raised when a journal template cannot be loaded or rendered."""


class JournalFileSystemError(JournalError):
    """Raised when a journal file cannot be written to the filesystem."""
