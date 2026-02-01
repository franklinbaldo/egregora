"""CLI error handling utilities."""

from collections.abc import Generator
from contextlib import contextmanager

import typer
from rich.console import Console

from egregora.agents.exceptions import EnrichmentError, ReaderError
from egregora.config.exceptions import (
    ApiKeyNotFoundError,
    ConfigError,
    InvalidConfigurationValueError,
    SiteStructureError,
)
from egregora.input_adapters.exceptions import UnknownAdapterError
from egregora.orchestration.exceptions import (
    ApiKeyInvalidError,
    CommandAnnouncementError,
    OutputSinkError,
    ProfileGenerationError,
)

console = Console()


@contextmanager
def handle_cli_errors(*, debug: bool = False) -> Generator[None, None, None]:
    """Context manager to handle CLI errors gracefully.

    Args:
        debug: If True, print full traceback. If False, print user-friendly error.

    """
    try:
        yield
    except (KeyboardInterrupt, SystemExit):
        raise
    except ApiKeyNotFoundError as e:
        if debug:
            raise
        console.print(f"[bold red]🔑 API Key Missing:[/bold red] {e}")
        console.print(
            "Please set the [bold]GOOGLE_API_KEY[/bold] environment variable.\n"
            "You can get one at [cyan]https://aistudio.google.com/app/apikey[/cyan]"
        )
        raise typer.Exit(1) from e
    except ApiKeyInvalidError as e:
        if debug:
            raise
        console.print(f"[bold red]🚫 API Key Invalid:[/bold red] {e}")
        if e.validation_errors:
            for err in e.validation_errors:
                console.print(f"  - {err}")
        console.print("Please check your API key and try again.")
        raise typer.Exit(1) from e
    except UnknownAdapterError as e:
        if debug:
            raise
        console.print(f"[bold red]🔌 Unknown Source Adapter:[/bold red] {e}")
        console.print("Please check your configuration or command line arguments.")
        raise typer.Exit(1) from e
    except InvalidConfigurationValueError as e:
        if debug:
            raise
        console.print(f"[bold red]⚙️ Invalid Configuration:[/bold red] {e}")
        raise typer.Exit(1) from e
    except SiteStructureError as e:
        if debug:
            raise
        console.print(f"[bold red]🏗️ Site Structure Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    except (CommandAnnouncementError, ProfileGenerationError, OutputSinkError) as e:
        if debug:
            raise
        console.print(f"[bold red]🚨 Processing Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    except EnrichmentError as e:
        if debug:
            raise
        console.print(f"[bold red]✨ Enrichment Failed:[/bold red] {e}")
        raise typer.Exit(1) from e
    except ReaderError as e:
        if debug:
            raise
        console.print(f"[bold red]📖 Reader Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    except ConfigError as e:
        if debug:
            raise
        console.print(f"[bold red]⚙️ Configuration Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        if debug:
            console.print_exception(show_locals=False)
            raise typer.Exit(1) from e

        console.print(f"[bold red]💥 An unexpected error occurred:[/bold red] {e}")
        console.print("[dim]Run with [bold]--debug[/bold] for more details.[/dim]")
        raise typer.Exit(1) from e
