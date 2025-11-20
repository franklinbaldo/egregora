"""CLI commands for viewing and managing pipeline run history."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.run_store import RunStore

console = Console()

runs_app = typer.Typer(
    name="runs",
    help="View and manage pipeline run history",
)


def get_storage(db_path: Path) -> DuckDBStorageManager:
    """Get a DuckDBStorageManager instance."""
    return DuckDBStorageManager(db_path=db_path)


@runs_app.command(name="tail")
def runs_tail(
    n: Annotated[int, typer.Option(help="Number of runs to show")] = 10,
    db_path: Annotated[Path, typer.Option(help="Runs database path")] = Path(".egregora-cache/runs.duckdb"),
) -> None:
    """Show last N runs."""
    # Check if database exists before trying to open
    if not db_path.exists():
        console.print(f"[yellow]No runs database found at {db_path}[/yellow]")
        console.print("[dim]Runs will be tracked after first pipeline execution[/dim]")
        return

    try:
        storage = get_storage(db_path)
        with RunStore(storage) as store:
            result = store.get_latest_runs(n)
            if not result:
                console.print("[yellow]No runs found[/yellow]")
                return

            table = Table(title=f"Last {len(result)} Runs", show_header=True, header_style="bold cyan")
            table.add_column("Run ID", style="dim", no_wrap=True)
            table.add_column("Stage", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("Started At", style="blue")
            table.add_column("Rows In", justify="right")
            table.add_column("Rows Out", justify="right")
            table.add_column("Duration", justify="right")

            for row in result:
                run_id, stage, status, started_at, rows_in, rows_out, duration = row
                status_text = _format_status(status)
                duration_text = f"{duration:.2f}s" if duration is not None else "-"
                rows_in_text = str(rows_in) if rows_in is not None else "-"
                rows_out_text = str(rows_out) if rows_out is not None else "-"
                run_id_short = str(run_id)[:8]
                table.add_row(
                    run_id_short,
                    stage,
                    status_text,
                    str(started_at),
                    rows_in_text,
                    rows_out_text,
                    duration_text,
                )
            console.print(table)
    except FileNotFoundError:
        console.print(f"[yellow]No runs database found at {db_path}[/yellow]")
        console.print("[dim]Runs will be tracked after first pipeline execution[/dim]")


def _format_status(status: str) -> str:
    """Return color-coded status string."""
    if status == "completed":
        return f"[green]{status}[/green]"
    if status == "failed":
        return f"[red]{status}[/red]"
    if status == "running":
        return f"[yellow]{status}[/yellow]"
    return status


def _build_run_panel_content(
    run_id,
    tenant_id,
    stage,
    status,
    error,
    parent_run_id,
    code_ref,
    config_hash,
    started_at,
    finished_at,
    duration_seconds,
    rows_in,
    rows_out,
    llm_calls,
    tokens,
    attrs,
    trace_id,
) -> str:
    """Build formatted panel content from run data."""
    lines = []
    status_display = _format_status(status)
    lines.append(f"[bold cyan]Run ID:[/bold cyan] {run_id}")
    if tenant_id:
        lines.append(f"[bold cyan]Tenant:[/bold cyan] {tenant_id}")
    lines.append(f"[bold cyan]Stage:[/bold cyan] {stage}")
    lines.append(f"[bold cyan]Status:[/bold cyan] {status_display}")
    lines.append("")
    lines.append("[bold]Timestamps:[/bold]")
    lines.append(f"  Started:  {started_at}")
    if finished_at:
        lines.append(f"  Finished: {finished_at}")
    if duration_seconds:
        lines.append(f"  Duration: {duration_seconds:.2f}s")
    lines.append("")
    if rows_in is not None or rows_out is not None or llm_calls or tokens:
        lines.append("[bold]Metrics:[/bold]")
        if rows_in is not None:
            lines.append(f"  Rows In:   {rows_in:,}")
        if rows_out is not None:
            lines.append(f"  Rows Out:  {rows_out:,}")
        if llm_calls:
            lines.append(f"  LLM Calls: {llm_calls:,}")
        if tokens:
            lines.append(f"  Tokens:    {tokens:,}")
        lines.append("")
    if parent_run_id or code_ref or config_hash:
        lines.append("[bold]Tracking:[/bold]")
        if parent_run_id:
            lines.append(f"  Parent: {parent_run_id}")
        if code_ref:
            lines.append(f"  Code:   {code_ref}")
        if config_hash:
            lines.append(f"  Config: {config_hash[:32]}...")
        lines.append("")
    if error:
        lines.append("[bold red]Error:[/bold red]")
        lines.append(f"  {error}")
        lines.append("")
    if trace_id:
        lines.append("[bold]Observability:[/bold]")
        lines.append(f"  Trace ID: {trace_id}")
    return "\n".join(lines)


@runs_app.command(name="show")
def runs_show(
    run_id: Annotated[str, typer.Argument(help="Run ID to show (full UUID or prefix)")],
    db_path: Annotated[Path, typer.Option(help="Runs database path")] = Path(".egregora-cache/runs.duckdb"),
) -> None:
    """Show detailed run info."""
    # Check if database exists before trying to open
    if not db_path.exists():
        console.print(f"[red]No runs database found at {db_path}[/red]")
        raise typer.Exit(1)

    try:
        storage = get_storage(db_path)
        with RunStore(storage) as store:
            result = store.get_run_by_id(run_id)

            if not result:
                console.print(f"[red]Run not found: {run_id}[/red]")
                raise typer.Exit(1)

            (
                run_id_full,
                tenant_id,
                stage,
                status,
                error,
                parent_run_id,
                code_ref,
                config_hash,
                started_at,
                finished_at,
                duration_seconds,
                rows_in,
                rows_out,
                llm_calls,
                tokens,
                attrs,
                trace_id,
            ) = result
            panel_content = _build_run_panel_content(
                run_id_full,
                tenant_id,
                stage,
                status,
                error,
                parent_run_id,
                code_ref,
                config_hash,
                started_at,
                finished_at,
                duration_seconds,
                rows_in,
                rows_out,
                llm_calls,
                tokens,
                attrs,
                trace_id,
            )
            panel = Panel(panel_content, title=f"[bold]Run Details: {stage}[/bold]", border_style="cyan")
            console.print(panel)
    except FileNotFoundError:
        console.print(f"[red]No runs database found at {db_path}[/red]")
        raise typer.Exit(1)
