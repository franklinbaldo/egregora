"""Database management CLI commands."""

from pathlib import Path
from typing import Annotated

import ibis
import typer
from rich.console import Console

from egregora.config import load_egregora_config
from egregora.database.migrations import migrate_documents_table
from egregora.database.utils import resolve_db_uri

db_app = typer.Typer(name="db", help="Database management commands.")
console = Console()

@db_app.command()
def migrate(
    site_root: Annotated[Path, typer.Argument(help="Site root directory containing .egregora.toml")],
) -> None:
    """Migrate the database schema to the latest version.

    This command ensures that the 'documents' table matches the current schema,
    adding any missing columns (e.g. doc_type, extensions).
    """
    site_root = site_root.expanduser().resolve()

    try:
        config = load_egregora_config(site_root)
    except Exception as e:
        console.print(f"[red]Failed to load configuration from {site_root}: {e}[/red]")
        raise typer.Exit(1) from e

    db_uri = config.database.pipeline_db
    if not db_uri:
        console.print("[red]No pipeline database configured.[/red]")
        raise typer.Exit(1)

    db_uri = resolve_db_uri(db_uri, site_root)

    console.print(f"[cyan]Connecting to database: {db_uri}[/cyan]")

    try:
        # Connect with Ibis
        con = ibis.connect(db_uri)

        # Run migration
        # migrate_documents_table handles connection abstraction (Ibis backend or raw connection)
        migrate_documents_table(con)

        console.print("[green]Migration complete.[/green]")

    except Exception as e:
        console.print(f"[red]Migration failed: {e}[/red]")
        raise typer.Exit(1) from e
