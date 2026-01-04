"""Core exceptions for the Egregora application."""


# Base exception for Egregora
class EgregoraError(Exception):
    """Base exception for all Egregora errors."""


# Slugify-specific exceptions
class SlugifyError(EgregoraError):
    """Base exception for slugify-related errors."""


class InvalidInputError(SlugifyError):
    """Raised when the input to a function is invalid."""
