"""Error Boundary pattern implementation for standardized error handling."""

import logging
from enum import Enum
from typing import Protocol

from egregora.exceptions import EgregoraError

logger = logging.getLogger(__name__)


class FailureStrategy(Enum):
    """Strategy for handling different types of failures."""

    FATAL = "fatal"
    """Stop pipeline immediately and raise exception."""

    WARN = "warn"
    """Continue pipeline, log warning, notify user."""

    SILENT = "silent"
    """Continue pipeline, log at debug level."""

    RETRY = "retry"
    """Retry operation with exponential backoff (handled by caller or decorator)."""


class ErrorBoundary(Protocol):
    """
    Define error handling policies for different operations.

    This centralizes error handling logic and makes behavior predictable.
    Each operation type has a clear failure strategy.
    """

    def handle_journal_error(self, e: Exception) -> None:
        """Handle journal persistence errors."""
        ...

    def handle_enrichment_error(self, e: Exception) -> None:
        """Handle media enrichment errors."""
        ...

    def handle_rag_error(self, e: Exception) -> None:
        """Handle RAG/vector search errors."""
        ...

    def handle_writer_error(self, e: Exception) -> None:
        """Handle Writer agent errors."""
        ...

    def handle_generic_error(self, e: Exception) -> None:
        """Handle generic pipeline errors."""
        ...


class DefaultErrorBoundary:
    """Default implementation of error boundary."""

    def __init__(self, logger_instance: logging.Logger | None = None) -> None:
        self.logger = logger_instance or logger

    def handle_journal_error(self, e: Exception) -> None:
        """
        Handle journal persistence errors.

        Strategy: FATAL
        Reason: Breaks idempotency guarantees.
        """
        self.logger.critical("Journal error: %s", e)
        if isinstance(e, EgregoraError):
            raise e
        msg = "Cannot proceed without journal"
        raise RuntimeError(msg) from e

    def handle_enrichment_error(self, e: Exception) -> None:
        """
        Handle media enrichment errors.

        Strategy: WARN
        Reason: Non-critical feature, user should know.
        """
        self.logger.warning("Enrichment failed: %s", e)
        # Continue processing (no raise)

    def handle_rag_error(self, e: Exception) -> None:
        """
        Handle RAG/vector search errors.

        Strategy: WARN
        Reason: Degrades to no-context mode gracefully.
        """
        self.logger.warning("RAG error: %s", e)
        # Continue processing (no raise)

    def handle_writer_error(self, e: Exception) -> None:
        """
        Handle Writer agent errors.

        Strategy: FATAL (after internal retries failed)
        Reason: Core feature.
        """
        self.logger.error("Writer error: %s", e)
        raise e

    def handle_generic_error(self, e: Exception) -> None:
        """
        Handle generic pipeline errors.

        Strategy: FATAL
        Reason: Unhandled exception.
        """
        self.logger.critical("Pipeline error: %s", e)
        raise e
