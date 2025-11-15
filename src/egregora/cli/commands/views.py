"""View management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from egregora.cli._app import app, console
from egregora.cli.commands.views_utils import ensure_view_registered, view_registry_context

views_app = typer.Typer(
    name="views",
    help="Manage database views and materialized views",
)
app.add_typer(views_app)


@views_app.command(name="list")
def views_list(
    db_path: Annotated[
        Path | None, typer.Option(help="Database file path (uses in-memory DB if not specified)")
    ] = None,
) -> None:
    """List all registered views."""
    with view_registry_context(db_path) as (_, registry):
        views = sorted(registry.list_views())

        if not views:
            console.print("[yellow]No views registered[/yellow]")
            return

        console.print(f"[cyan]Registered views ({len(views)}):[/cyan]")
        console.print()

        for view_name in views:
            view = registry.get_view(view_name)
            materialized = "📊 materialized" if getattr(view, "materialized", False) else "👁️  view"
            console.print(f"  • [bold]{view_name}[/bold] [{materialized}]")

            description = getattr(view, "description", "")
            if description:
                console.print(f"    {description}", style="dim")

            dependencies = getattr(view, "dependencies", None)
            if dependencies:
                console.print(f"    Dependencies: {', '.join(dependencies)}", style="dim")

            console.print()


@views_app.command(name="create")
def views_create(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
    force: Annotated[bool, typer.Option("--force", "-f", help="Drop existing views before creating")]
    = False,
) -> None:
    """Create all registered views in the database."""
    with view_registry_context(
        db_path,
        table_name=table_name,
        require_db=True,
        require_table=True,
    ) as (_, registry):
        try:
            console.print(f"[cyan]Creating {len(registry.list_views())} views...[/cyan]")
            registry.create_all(force=force)
            console.print(f"[green]✅ Created {len(registry.list_views())} views[/green]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error creating views: {exc}[/red]")
            raise typer.Exit(1) from exc


@views_app.command(name="refresh")
def views_refresh(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    view_name: Annotated[
        str | None, typer.Option(help="Specific view to refresh (refreshes all if not specified)")
    ] = None,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
) -> None:
    """Refresh materialized views with fresh data."""
    with view_registry_context(db_path, table_name=table_name, require_db=True) as (_, registry):
        try:
            if view_name:
                ensure_view_registered(registry, view_name, require_materialized=True)
                console.print(f"[cyan]Refreshing view: {view_name}...[/cyan]")
                registry.refresh(view_name)
                console.print(f"[green]✅ Refreshed {view_name}[/green]")
                return

            materialized_views = [
                name
                for name in registry.list_views()
                if getattr(registry.get_view(name), "materialized", False)
            ]

            if not materialized_views:
                console.print("[yellow]No materialized views to refresh[/yellow]")
                return

            console.print(f"[cyan]Refreshing {len(materialized_views)} materialized views...[/cyan]")
            registry.refresh_all()
            console.print(f"[green]✅ Refreshed {len(materialized_views)} views[/green]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error refreshing views: {exc}[/red]")
            raise typer.Exit(1) from exc


@views_app.command(name="drop")
def views_drop(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    view_name: Annotated[
        str | None, typer.Option(help="Specific view to drop (drops all if not specified)")
    ] = None,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")]
    = False,
) -> None:
    """Drop views from the database."""
    with view_registry_context(db_path, table_name=table_name, require_db=True) as (_, registry):
        try:
            if view_name:
                ensure_view_registered(registry, view_name)
                if not force:
                    console.print(f"[yellow]About to drop view: {view_name}[/yellow]")
                    confirm = typer.confirm("Continue?")
                    if not confirm:
                        console.print("[cyan]Cancelled[/cyan]")
                        raise typer.Exit(0)

                registry.drop(view_name)
                console.print(f"[green]✅ Dropped {view_name}[/green]")
                return

            views = registry.list_views()
            view_count = len(views)

            if view_count == 0:
                console.print("[yellow]No views to drop[/yellow]")
                return

            if not force:
                console.print(f"[yellow]About to drop {view_count} views[/yellow]")
                confirm = typer.confirm("Continue?")
                if not confirm:
                    console.print("[cyan]Cancelled[/cyan]")
                    raise typer.Exit(0)

            registry.drop_all()
            console.print(f"[green]✅ Dropped {view_count} views[/green]")
        except typer.Exit:
            raise
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error dropping views: {exc}[/red]")
            raise typer.Exit(1) from exc
