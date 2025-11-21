"""A module for Egregora's command-line interface."""

from egregora.cli.main import app
from egregora.cli.runs import runs_app

__all__ = ["app", "main", "runs_app"]


def main() -> None:
    """Entry point for the CLI."""
    app.add_typer(runs_app)
    app()
