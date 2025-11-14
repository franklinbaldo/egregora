"""Typer-based CLI for Egregora v2."""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.logging import RichHandler

app = typer.Typer(
    name="egregora",
    help="Ultra-simple WhatsApp to blog pipeline with LLM-powered content generation",
    add_completion=False,
)

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger(__name__)


@app.callback()
def _initialize_cli() -> None:
    """Initialize CLI (placeholder for future setup)."""


# Import command modules to register Typer commands
from .commands import doctor as _doctor  # noqa: F401
from .commands import init as _init  # noqa: F401
from .commands import runs as _runs  # noqa: F401
from .commands import views as _views  # noqa: F401
from .commands import write as _write  # noqa: F401

__all__ = ["app", "console", "logger", "main"]


def main() -> None:
    """Entry point for the CLI."""
    app()
