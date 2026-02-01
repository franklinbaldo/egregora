"""Error Boundary Pattern for standardized failure handling in orchestration."""

import logging
from enum import Enum
from typing import Protocol

from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


class FailureStrategy(Enum):
    """Strategy for handling different types of failures."""

    FATAL = "fatal"
    """Stop pipeline immediately and raise exception."""

    WARN = "warn"
    """Continue pipeline, log warning, notify user."""

    SILENT = "silent"
    """Continue pipeline, log at debug level."""

    RETRY = "retry"
    """Retry operation (handled by caller or decorator, falls back to FATAL/WARN)."""


class ErrorBoundary(Protocol):
    """Define error handling policies for different operations.

    This centralizes error handling logic and makes behavior predictable.
    Each operation type has a clear failure strategy.
    """

    def handle_journal_error(self, e: Exception, context: str = "") -> None:
        """Handle journal persistence errors."""
        ...

    def handle_enrichment_error(self, e: Exception, context: str = "") -> None:
        """Handle media enrichment errors."""
        ...

    def handle_writer_error(self, e: Exception, context: str = "") -> None:
        """Handle Writer agent errors."""
        ...

    def handle_profile_error(self, e: Exception, context: str = "") -> None:
        """Handle Profile generator errors."""
        ...

    def handle_command_error(self, e: Exception, context: str = "") -> None:
        """Handle Command processing errors."""
        ...

    def handle_output_error(self, e: Exception, context: str = "") -> None:
        """Handle Output persistence errors."""
        ...


class DefaultErrorBoundary:
    """Default implementation of error boundary."""

    def handle_journal_error(self, e: Exception, context: str = "") -> None:
        """Strategy: FATAL. Breaks idempotency guarantees."""
        msg = f"Journal error ({context}): {e}"
        logger.critical(msg)
        console.print(f"[bold red]❌ Critical Journal Error:[/bold red] {msg}")
        raise e

    def handle_enrichment_error(self, e: Exception, context: str = "") -> None:
        """Strategy: WARN. Non-critical feature."""
        msg = f"Enrichment failed ({context}): {e}"
        logger.warning(msg)
        console.print(f"[yellow]⚠️  Enrichment warning:[/yellow] {msg}")
        # Does not raise

    def handle_writer_error(self, e: Exception, context: str = "") -> None:
        """Strategy: FATAL (after internal retries). Core feature."""
        msg = f"Writer error ({context}): {e}"
        logger.error(msg)
        console.print(f"[bold red]❌ Writer Error:[/bold red] {msg}")
        raise e

    def handle_profile_error(self, e: Exception, context: str = "") -> None:
        """Strategy: WARN. Secondary feature."""
        msg = f"Profile generation failed ({context}): {e}"
        logger.warning(msg)
        console.print(f"[yellow]⚠️  Profile warning:[/yellow] {msg}")
        # Does not raise

    def handle_command_error(self, e: Exception, context: str = "") -> None:
        """Strategy: WARN. User input might be malformed, shouldn't crash pipeline."""
        msg = f"Command processing failed ({context}): {e}"
        logger.warning(msg)
        console.print(f"[yellow]⚠️  Command warning:[/yellow] {msg}")
        # Does not raise

    def handle_output_error(self, e: Exception, context: str = "") -> None:
        """Strategy: FATAL. Data loss risk."""
        msg = f"Output persistence failed ({context}): {e}"
        logger.critical(msg)
        console.print(f"[bold red]❌ Output Error:[/bold red] {msg}")
        raise e
