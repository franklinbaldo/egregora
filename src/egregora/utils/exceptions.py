"""Backward-compatible exception aliases for legacy imports.

This module preserves the historical ``egregora.utils.exceptions`` import path
by re-exporting exception classes from their current modules. Prefer importing
from the owning modules (e.g., ``egregora.orchestration.exceptions``) in new
code, but keep this file to avoid breaking existing users and documentation.
"""

from egregora.knowledge.exceptions import (
    AuthorsError,
    AuthorsFileError,
    AuthorsFileLoadError,
    AuthorsFileParseError,
    AuthorsFileSaveError,
    InvalidAliasError,
    ProfileError,
    ProfileNotFoundError,
    ProfileParseError,
)
from egregora.orchestration.exceptions import (
    ApiKeyInvalidError,
    ApiKeyMissingError,
    CacheDeserializationError,
    CacheError,
    CacheKeyNotFoundError,
    CachePayloadTypeError,
    CommandProcessingError,
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    EnrichmentError,
    InvalidDateArgumentError,
    InvalidTimezoneArgumentError,
    OrchestrationError,
    OutputSinkError,
    PipelineSetupError,
    ProfileGenerationError,
    SourceNotFoundError,
    WindowError,
    WindowSizeError,
    WindowSplitError,
)
from egregora.utils.datetime_utils import DateTimeError, DateTimeParsingError, InvalidDateTimeInputError


# Base exception for Egregora
class EgregoraError(Exception):
    """Base exception for all Egregora errors."""


__all__ = [
    # Orchestration
    "ApiKeyInvalidError",
    "ApiKeyMissingError",
    # Knowledge / profiles
    "AuthorsError",
    "AuthorsFileError",
    "AuthorsFileLoadError",
    "AuthorsFileParseError",
    "AuthorsFileSaveError",
    "CacheDeserializationError",
    "CacheError",
    "CacheKeyNotFoundError",
    "CachePayloadTypeError",
    "CommandProcessingError",
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    # Datetime utilities
    "DateTimeError",
    "DateTimeParsingError",
    # Base exceptions
    "EgregoraError",
    "EnrichmentError",
    "InvalidAliasError",
    "InvalidDateArgumentError",
    "InvalidDateTimeInputError",
    "InvalidTimezoneArgumentError",
    "OrchestrationError",
    "OutputSinkError",
    "PipelineSetupError",
    "ProfileError",
    "ProfileGenerationError",
    "ProfileNotFoundError",
    "ProfileParseError",
    "SourceNotFoundError",
    "WindowError",
    "WindowSizeError",
    "WindowSplitError",
]
