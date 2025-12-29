"""Custom exceptions for the agents module."""


class AgentError(Exception):
    """Base exception for all agent-related errors."""


class EnrichmentError(AgentError):
    """Base exception for errors during the enrichment process."""


class MediaStagingError(EnrichmentError):
    """Raised when a media file cannot be staged for enrichment."""
