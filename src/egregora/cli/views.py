"""CLI commands for managing database views."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()

views_app = typer.Typer(
    name="views",
    help="Manage database views and materialized views",
)


@views_app.command(name="list")
def views_list(
    db_path: Annotated[
        Path | None, typer.Option(help="Database file path (uses in-memory DB if not specified)")
    ] = None,
) -> None:
    """List all registered views."""
    import duckdb

    from egregora.database.views import ViewRegistry, register_common_views

    conn = duckdb.connect(str(db_path) if db_path else ":memory:")
    try:
        registry = ViewRegistry(conn)
        register_common_views(registry)
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
    finally:
        conn.close()


@views_app.command(name="create")
def views_create(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
    force: Annotated[bool, typer.Option("--force", "-f", help="Drop existing views before creating")] = False,
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
    except Exception as e:
        console.print(f"[red]Error creating views: {e}[/red]")
        raise typer.Exit(1) from e
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
    import duckdb

    from egregora.database.views import ViewRegistry, register_common_views

    if not db_path.exists():
        console.print(f"[red]Error: Database file not found: {db_path}[/red]")
        raise typer.Exit(1)

    conn = duckdb.connect(str(db_path))
    registry = ViewRegistry(conn)
    register_common_views(registry, table_name=table_name)

    if view_name:
        if view_name not in registry.list_views():
            conn.close()
            console.print(f"[red]Error: View '{view_name}' not registered[/red]")
            console.print(f"Available views: {', '.join(registry.list_views())}")
            raise typer.Exit(1)
        view = registry.get_view(view_name)
        if not view.materialized:
            conn.close()
            console.print(f"[yellow]Warning: '{view_name}' is not materialized (cannot refresh)[/yellow]")
            raise typer.Exit(1)
    try:
        if view_name:
            console.print(f"[cyan]Refreshing view: {view_name}...[/cyan]")
            registry.refresh(view_name)
            console.print(f"[green]✅ Refreshed {view_name}[/green]")
        else:
            materialized_views = [name for name, view in registry.views.items() if view.materialized]
            if not materialized_views:
                console.print("[yellow]No materialized views to refresh[/yellow]")
                return
            console.print(f"[cyan]Refreshing {len(materialized_views)} materialized views...[/cyan]")
            registry.refresh_all()
            console.print(f"[green]✅ Refreshed {len(materialized_views)} views[/green]")
    except Exception as e:
        console.print(f"[red]Error refreshing views: {e}[/red]")
        raise typer.Exit(1) from e
    finally:
        conn.close()


@views_app.command(name="drop")
def views_drop(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    view_name: Annotated[
        str | None, typer.Option(help="Specific view to drop (drops all if not specified)")
    ] = None,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    """Drop views from the database."""
    import duckdb

    from egregora.database.views import ViewRegistry, register_common_views

    if not db_path.exists():
        console.print(f"[red]Error: Database file not found: {db_path}[/red]")
        raise typer.Exit(1)

    conn = duckdb.connect(str(db_path))
    registry = ViewRegistry(conn)
    register_common_views(registry, table_name=table_name)

    if view_name:
        if view_name not in registry.list_views():
            conn.close()
            console.print(f"[red]Error: View '{view_name}' not registered[/red]")
            console.print(f"Available views: {', '.join(registry.list_views())}")
            raise typer.Exit(1)
        if not force:
            console.print(f"[yellow]About to drop view: {view_name}[/yellow]")
            confirm = typer.confirm("Continue?")
            if not confirm:
                conn.close()
                console.print("[cyan]Cancelled[/cyan]")
                raise typer.Exit(0)
    else:
        view_count = len(registry.list_views())
        if view_count == 0:
            conn.close()
            console.print("[yellow]No views to drop[/yellow]")
            return
        if not force:
            console.print(f"[yellow]About to drop {view_count} views[/yellow]")
            confirm = typer.confirm("Continue?")
            if not confirm:
                conn.close()
                console.print("[cyan]Cancelled[/cyan]")
                raise typer.Exit(0)
    try:
        if view_name:
            registry.drop(view_name)
            console.print(f"[green]✅ Dropped {view_name}[/green]")
        else:
            view_count = len(registry.list_views())
            registry.drop_all()
            console.print(f"[green]✅ Dropped {view_count} views[/green]")
    except Exception as e:
        console.print(f"[red]Error dropping views: {e}[/red]")
        raise typer.Exit(1) from e
    finally:
        conn.close()
