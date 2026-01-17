"""CLI for persona management."""

import asyncio
from pathlib import Path
from typing import Annotated

import ibis
import typer
from rich.console import Console
from rich.panel import Panel

from egregora.agents.profile.persona import extract_persona
from egregora.config import load_egregora_config
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.utils import resolve_db_uri

persona_app = typer.Typer(name="persona", help="Manage and extract user personas")
console = Console()


@persona_app.command("analyze")
def analyze(
    site_root: Annotated[Path, typer.Argument(help="Site root directory containing .egregora config")],
    author_uuid: Annotated[str, typer.Argument(help="Author UUID to analyze")],
    limit: Annotated[int, typer.Option(help="Max messages to analyze")] = 100,
    model: Annotated[str, typer.Option(help="Model to use")] = "google-gla:gemini-1.5-flash",
) -> None:
    """Analyze an author's message history and generate a structured persona."""
    site_root = site_root.expanduser().resolve()

    # 1. Load config
    try:
        config = load_egregora_config(site_root)
    except Exception as e:
        console.print(f"[red]Failed to load config from {site_root}: {e}[/red]")
        raise typer.Exit(1) from e

    # 2. Connect to DB
    try:
        db_uri = config.database.pipeline_db
        # resolve_db_uri handles the logic for resolving path relative to site_root
        resolved_uri = resolve_db_uri(db_uri, site_root)

        # Connect with read-only=True if possible, but DuckDBStorageManager usually expects RW.
        # However, for analysis we only read. But DuckDBStorageManager constructor/helpers might imply RW.
        # We'll use standard connection.
        backend = ibis.connect(resolved_uri)
        storage = DuckDBStorageManager.from_ibis_backend(backend)
    except Exception as e:
        console.print(f"[red]Failed to connect to database: {e}[/red]")
        raise typer.Exit(1) from e

    # 3. Fetch messages
    try:
        if not storage.table_exists("messages"):
            console.print("[red]Table 'messages' not found in database. Run 'egregora write' first.[/red]")
            raise typer.Exit(1)

        t = storage.read_table("messages")

        # Filter by author and limit
        # Note: 'author_uuid' column exists in STAGING_MESSAGES_SCHEMA
        # We sort by timestamp descending to get most recent messages
        query = (
            t.filter(t.author_uuid == author_uuid)
            .order_by(t.ts.desc())
            .limit(limit)
            .select("text", "author_raw")
        )

        rows = query.execute().to_dict(orient="records")

        if not rows:
            console.print(f"[yellow]No messages found for author {author_uuid}[/yellow]")
            return

        # Filter out None texts
        messages = [r["text"] for r in rows if r["text"]]
        if not messages:
            console.print(f"[yellow]No text messages found for author {author_uuid} (only media?)[/yellow]")
            return

        author_name = rows[0]["author_raw"] or "Unknown"

    except Exception as e:
        console.print(f"[red]Error querying messages: {e}[/red]")
        raise typer.Exit(1) from e

    # 4. Extract Persona
    console.print(f"[cyan]Analyzing {len(messages)} messages for {author_name}...[/cyan]")

    try:
        persona = asyncio.run(extract_persona(messages, author_name, model))
    except Exception as e:
        console.print(f"[red]AI Analysis failed: {e}[/red]")
        raise typer.Exit(1) from e

    # 5. Output
    console.print(
        Panel(persona.model_dump_json(indent=2), title=f"Persona: {author_name}", border_style="green")
    )
