"""Main entry point for the Typer-based CLI for Egregora."""

from .main import app
from .views import views_app
from .runs import runs_app


def main() -> None:
    """Entry point for the CLI."""
    app.add_typer(views_app)
    app.add_typer(runs_app)
    app()
