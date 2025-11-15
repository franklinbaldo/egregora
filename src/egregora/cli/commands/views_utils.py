"""Shared utilities for CLI view commands."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import duckdb
import typer

from egregora.cli._app import console
from egregora.database.views import ViewRegistry, register_common_views


@contextmanager
def view_registry_context(
    db_path: Path | None,
    *,
    table_name: str = "messages",
    require_db: bool = False,
    require_table: bool = False,
    read_only: bool = False,
) -> Iterator[tuple[duckdb.DuckDBPyConnection, ViewRegistry]]:
    """Yield a configured DuckDB connection and registered view registry."""
    if db_path is None:
        if require_db:
            console.print("[red]Error: Database path is required for this command[/red]")
            raise typer.Exit(1)
        conn = duckdb.connect(":memory:")
    else:
        if require_db and not db_path.exists():
            console.print(f"[red]Error: Database file not found: {db_path}[/red]")
            raise typer.Exit(1)
        conn = duckdb.connect(str(db_path), read_only=read_only)

    try:
        if require_table:
            tables = conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
            table_names = sorted(row[0] for row in tables)
            if table_name not in table_names:
                console.print(f"[red]Error: Table '{table_name}' not found in database[/red]")
                if table_names:
                    console.print(f"Available tables: {', '.join(table_names)}")
                raise typer.Exit(1)

        registry = ViewRegistry(conn)
        register_common_views(registry, table_name=table_name)
        yield conn, registry
    finally:
        conn.close()


def ensure_view_registered(
    registry: ViewRegistry,
    view_name: str,
    *,
    require_materialized: bool = False,
) -> Any:
    """Return a registered view or terminate with a helpful error message."""
    try:
        view = registry.get_view(view_name)
    except Exception as exc:  # noqa: BLE001
        available = []
        try:
            available = registry.list_views()
        except Exception:  # noqa: BLE001
            pass
        console.print(f"[red]Error: View '{view_name}' not registered[/red]")
        if available:
            console.print(f"Available views: {', '.join(available)}")
        raise typer.Exit(1) from exc

    if require_materialized and not getattr(view, "materialized", False):
        console.print(f"[yellow]Warning: '{view_name}' is not materialized (cannot refresh)[/yellow]")
        raise typer.Exit(1)

    return view


__all__ = ["ensure_view_registered", "view_registry_context"]
