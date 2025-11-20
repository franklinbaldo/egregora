from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.views import COMMON_VIEWS, get_view_builder, list_common_views

console = Console()

views_app = typer.Typer(
    name="views",
    help="Inspect and materialize common pipeline view transformations",
)


def _select_builders(view_name: str | None) -> dict[str, callable]:
    if view_name is None:
        return COMMON_VIEWS

    try:
        builder = get_view_builder(view_name)
    except KeyError as exc:
        console.print(f"[red]Unknown view: {view_name}[/red]")
        console.print(f"Available views: {', '.join(list_common_views())}")
        raise typer.Exit(code=1) from exc

    return {view_name: builder}


def _ensure_storage(db_path: Path, table_name: str) -> DuckDBStorageManager:
    if not db_path.exists():
        console.print(f"[red]Error: Database file not found: {db_path}[/red]")
        raise typer.Exit(code=1)

    storage = DuckDBStorageManager(db_path=db_path)
    if not storage.table_exists(table_name):
        storage.close()
        console.print(f"[red]Error: Table '{table_name}' not found in database[/red]")
        raise typer.Exit(code=1)

    return storage


@views_app.command(name="list")
def views_list() -> None:
    """List available view builders."""
    view_names = list_common_views()
    if not view_names:
        console.print("[yellow]No views available[/yellow]")
        return

    console.print(f"[cyan]Registered views ({len(view_names)}):[/cyan]")
    console.print()
    for name in view_names:
        builder = COMMON_VIEWS[name]
        doc = (builder.__doc__ or "").strip().splitlines()
        summary = doc[0] if doc else "No description"
        console.print(f"  • [bold]{name}[/bold]")
        console.print(f"    {summary}", style="dim")
        console.print()


@views_app.command(name="create")
def views_create(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    table_name: Annotated[str, typer.Option(help="Name of the input table")] = "messages",
    view_name: Annotated[
        str | None,
        typer.Option(
            "--view", help="Optional view to materialize (defaults to all common views)", show_default=False
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Drop output tables if they already exist")
    ] = False,
) -> None:
    """Materialize view outputs as DuckDB tables."""
    storage = _ensure_storage(db_path, table_name)
    builders = _select_builders(view_name)

    try:
        for name, builder in builders.items():
            if force and storage.table_exists(name):
                storage.drop_table(name)
            elif storage.table_exists(name):
                console.print(
                    f"[yellow]Skipping {name}: table already exists (use --force to overwrite)[/yellow]"
                )
                continue

            console.print(f"[cyan]Creating view: {name}[/cyan]")
            storage.execute_view(name, builder, table_name, checkpoint=True)
        console.print(f"[green]✅ Materialized {len(builders)} view(s)[/green]")
    finally:
        storage.close()


@views_app.command(name="refresh")
def views_refresh(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    table_name: Annotated[str, typer.Option(help="Name of the input table")] = "messages",
    view_name: Annotated[
        str | None,
        typer.Option(
            "--view", help="Optional view to refresh (defaults to all common views)", show_default=False
        ),
    ] = None,
) -> None:
    """Rebuild materialized view tables."""
    views_create(db_path, table_name=table_name, view_name=view_name, force=True)


@views_app.command(name="drop")
def views_drop(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    view_name: Annotated[
        str | None,
        typer.Option(
            "--view", help="Optional view to drop (defaults to all common views)", show_default=False
        ),
    ] = None,
) -> None:
    """Drop materialized view tables."""
    if not db_path.exists():
        console.print(f"[red]Error: Database file not found: {db_path}[/red]")
        raise typer.Exit(code=1)

    builders = _select_builders(view_name)
    with DuckDBStorageManager(db_path=db_path) as storage:
        dropped = 0
        for name in builders:
            if storage.table_exists(name):
                storage.drop_table(name)
                dropped += 1
        if dropped:
            console.print(f"[green]✅ Dropped {dropped} view table(s)[/green]")
        else:
            console.print("[yellow]No view tables found to drop[/yellow]")
