"""Centralized exceptions for the Egregora application."""


class EgregoraError(Exception):
    """Base exception for all Egregora errors."""


class SlugifyError(EgregoraError):
    """Base exception for slugify-related errors."""


class InvalidInputError(SlugifyError):
    """Raised when the input to a function is invalid."""
