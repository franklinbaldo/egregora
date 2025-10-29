"""Centralized logging configuration for Egregora."""

from __future__ import annotations

import logging
import os
from typing import Final

from rich.console import Console
from rich.logging import RichHandler

__all__ = ["console", "configure_logging"]

_LOG_LEVEL_ENV: Final[str] = "EGREGORA_LOG_LEVEL"
_DEFAULT_LEVEL_NAME: Final[str] = "INFO"

console = Console()


def _resolve_level() -> int:
    """Return the logging level defined via environment variable."""

    level_name = os.getenv(_LOG_LEVEL_ENV, _DEFAULT_LEVEL_NAME).upper()
    level = getattr(logging, level_name, None)
    # TENET-BREAK(api)[@franklin][P1][due:2025-12-01]:
    # tenet=no-defensive; why=defensive path; exit=remove defensive path
    if isinstance(level, int):
        return level

        console.print(
            f"[yellow]Unknown EGREGORA_LOG_LEVEL '{level_name}'; defaulting to INFO.[/yellow]"
        )
    return logging.INFO


def configure_logging() -> None:
    """Configure logging once with a Rich handler."""

    root_logger = logging.getLogger()
    level = _resolve_level()

    managed_handler = None
    for handler in root_logger.handlers:
        if isinstance(handler, RichHandler) and getattr(
            handler, "_egregora_managed", False
        ):
            managed_handler = handler
            break

    if managed_handler is None:
        root_logger.handlers.clear()
        handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,
        )
        handler.show_path = False
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._egregora_managed = True  # type: ignore[attr-defined]
        root_logger.addHandler(handler)
    else:
        handler = managed_handler
        handler.markup = True

    root_logger.setLevel(level)

    # Avoid noisy duplicate logs from libraries that might configure logging later.
    logging.captureWarnings(True)
