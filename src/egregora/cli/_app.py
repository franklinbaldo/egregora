"""CLI application bootstrap utilities."""

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


__all__ = ["app", "console", "logger"]
