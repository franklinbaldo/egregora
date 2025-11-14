"""Shared helpers for DuckDB view management commands."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from duckdb import DuckDBPyConnection
    from egregora.database.views import ViewRegistry


def _connect_duckdb(db_path: Path | None, *, read_only: bool) -> "DuckDBPyConnection":
    """Return a DuckDB connection for the provided path."""
    import duckdb

    target = str(db_path) if db_path else ":memory:"
    return duckdb.connect(target, read_only=read_only)


def _create_registry(conn: "DuckDBPyConnection", table_name: str) -> "ViewRegistry":
    """Instantiate and populate a view registry for the given connection."""
    from egregora.database.views import ViewRegistry, register_common_views

    registry = ViewRegistry(conn)
    register_common_views(registry, table_name=table_name)
    return registry


@contextmanager
def view_registry_context(
    console: Console,
    db_path: Path | None,
    *,
    table_name: str = "messages",
    require_db: bool = False,
    read_only: bool = False,
) -> Iterator[tuple["DuckDBPyConnection", "ViewRegistry"]]:
    """Yield a DuckDB connection and populated view registry with shared error handling."""
    if require_db:
        if db_path is None:
            console.print("[red]Error: Database file path is required[/red]")
            raise typer.Exit(1)
        if not db_path.exists():
            console.print(f"[red]Error: Database file not found: {db_path}[/red]")
            raise typer.Exit(1)

    try:
        conn = _connect_duckdb(db_path, read_only=read_only)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error connecting to database: {exc}[/red]")
        raise typer.Exit(1) from exc

    try:
        registry = _create_registry(conn, table_name)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error preparing view registry: {exc}[/red]")
        conn.close()
        raise typer.Exit(1) from exc

    try:
        yield conn, registry
    finally:
        conn.close()


def ensure_view_registered(
    console: Console, registry: "ViewRegistry", view_name: str
) -> None:
    """Validate the requested view exists, printing helpful diagnostics when missing."""
    if view_name not in registry.list_views():
        console.print(f"[red]Error: View '{view_name}' not registered[/red]")
        console.print(f"Available views: {', '.join(registry.list_views())}")
        raise typer.Exit(1)
