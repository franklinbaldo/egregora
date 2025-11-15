"""Site initialization commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from egregora.cli._app import app, console
from egregora.init import ensure_mkdocs_project


@app.command()
def init(
    output_dir: Annotated[Path, typer.Argument(help="Directory path for the new site (e.g., 'my-blog')")],
) -> None:
    """Initialize a new MkDocs site scaffold for serving Egregora posts."""
    site_root = output_dir.resolve()
    docs_dir, mkdocs_created = ensure_mkdocs_project(site_root)
    if mkdocs_created:
        console.print(
            Panel(
                f"[bold green]✅ MkDocs site scaffold initialized successfully![/bold green]\n\n📁 Site root: {site_root}\n📝 Docs directory: {docs_dir}\n\n[bold]Next steps:[/bold]\n• Install MkDocs: [cyan]pip install 'mkdocs-material[imaging]'[/cyan]\n• Change to site directory: [cyan]cd {output_dir}[/cyan]\n• Serve the site: [cyan]mkdocs serve[/cyan]\n• Process WhatsApp export: [cyan]egregora write export.zip --output={output_dir}[/cyan]",
                title="🛠️ Initialization Complete",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold yellow]⚠️ MkDocs site already exists at {site_root}[/bold yellow]\n\n📁 Using existing setup:\n• Docs directory: {docs_dir}\n\n[bold]To update or regenerate:[/bold]\n• Manually edit [cyan]mkdocs.yml[/cyan] or remove it to reinitialize.",
                title="📁 Site Exists",
                border_style="yellow",
            )
        )
