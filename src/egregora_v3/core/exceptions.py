"""Core exceptions for the Egregora v3 application."""


class EgregoraError(Exception):
    """Base exception for all Egregora errors."""


class SlugifyError(EgregoraError):
    """Base exception for slugify-related errors."""


class InvalidInputError(SlugifyError):
    """Raised when the input to a function is invalid."""
