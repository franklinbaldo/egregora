"""A module for Egregora's command-line interface."""

from egregora.cli.main import app

__all__ = ["app", "main"]


def main() -> None:
    """Entry point for the CLI."""
    app()
