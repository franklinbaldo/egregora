"""Custom exceptions for the agents module."""

from egregora.exceptions import EgregoraError


class AgentError(EgregoraError):
    """Base exception for all agent-related errors."""


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


class ReaderError(AgentError):
    """Base exception for reader agent errors."""


class ReaderConfigurationError(ReaderError):
    """Raised when reader configuration is invalid or missing resources."""


class ReaderInputError(ReaderError):
    """Raised when input data for reader is insufficient or invalid."""


class ReaderExecutionError(ReaderError):
    """Raised when reader execution fails."""
