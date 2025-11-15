"""Typer-based CLI for Egregora."""

from __future__ import annotations

from ._app import app
from .commands import doctor as _doctor  # noqa: F401
from .commands import init as _init  # noqa: F401
from .commands import runs as _runs  # noqa: F401
from .commands import views as _views  # noqa: F401
from .commands import write as _write  # noqa: F401

__all__ = ["app", "main"]


def main() -> None:
    """Entry point for the CLI."""
    app()
