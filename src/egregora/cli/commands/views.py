"""View management commands for the CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from egregora.cli import app, console
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
    with view_registry_context(console, db_path) as (_, registry):
        views = registry.list_views()

        if not views:
            console.print("[yellow]No views registered[/yellow]")
            return

        console.print(f"[cyan]Registered views ({len(views)}):[/cyan]")
        console.print()

        for view_name in sorted(views):
            view = registry.get_view(view_name)
            materialized = "📊 materialized" if view.materialized else "👁️  view"
            console.print(f"  • [bold]{view_name}[/bold] [{materialized}]")

            if view.description:
                console.print(f"    {view.description}", style="dim")

            if view.dependencies:
                deps = ", ".join(view.dependencies)
                console.print(f"    Dependencies: {deps}", style="dim")

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
    import duckdb

    from egregora.database.views import ViewRegistry, register_common_views

    if not db_path.exists():
        console.print(f"[red]Error: Database file not found: {db_path}[/red]")
        raise typer.Exit(1)

    conn = duckdb.connect(str(db_path))

    tables = conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
    table_names = [t[0] for t in tables]

    if table_name not in table_names:
        conn.close()
        console.print(f"[red]Error: Table '{table_name}' not found in database[/red]")
        console.print(f"Available tables: {', '.join(table_names)}")
        raise typer.Exit(1)

    try:
        registry = ViewRegistry(conn)
        register_common_views(registry, table_name=table_name)

        console.print(f"[cyan]Creating {len(registry.list_views())} views...[/cyan]")
        registry.create_all(force=force)

        console.print(f"[green]✅ Created {len(registry.list_views())} views[/green]")

    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error creating views: {exc}[/red]")
        raise typer.Exit(1) from exc
    finally:
        conn.close()


@views_app.command(name="refresh")
def views_refresh(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    view_name: Annotated[
        str | None, typer.Option(help="Specific view to refresh (refreshes all if not specified)")
    ] = None,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
) -> None:
    """Refresh materialized views with fresh data."""
    with view_registry_context(console, db_path, table_name=table_name, require_db=True) as (_, registry):
        if view_name:
            ensure_view_registered(console, registry, view_name)
            view = registry.get_view(view_name)
            if not view.materialized:
                console.print(f"[yellow]Warning: '{view_name}' is not materialized (cannot refresh)[/yellow]")
                raise typer.Exit(1)

            console.print(f"[cyan]Refreshing view: {view_name}...[/cyan]")
            registry.refresh(view_name)
            console.print(f"[green]✅ Refreshed {view_name}[/green]")
            return

        materialized_views = [name for name, view in registry.views.items() if view.materialized]

        if not materialized_views:
            console.print("[yellow]No materialized views to refresh[/yellow]")
            return

        console.print(f"[cyan]Refreshing {len(materialized_views)} materialized views...[/cyan]")
        registry.refresh_all()
        console.print(f"[green]✅ Refreshed {len(materialized_views)} views[/green]")


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
    with view_registry_context(console, db_path, table_name=table_name, require_db=True) as (_, registry):
        if view_name:
            ensure_view_registered(console, registry, view_name)
            if not force:
                console.print(f"[yellow]About to drop view: {view_name}[/yellow]")
                if not typer.confirm("Continue?"):
                    console.print("[cyan]Cancelled[/cyan]")
                    raise typer.Exit(0)

            registry.drop(view_name)
            console.print(f"[green]✅ Dropped {view_name}[/green]")
            return

        view_count = len(registry.list_views())
        if view_count == 0:
            console.print("[yellow]No views to drop[/yellow]")
            return

        if not force:
            console.print(f"[yellow]About to drop {view_count} views[/yellow]")
            if not typer.confirm("Continue?"):
                console.print("[cyan]Cancelled[/cyan]")
                raise typer.Exit(0)

        registry.drop_all()
        console.print(f"[green]✅ Dropped {view_count} views[/green]")
