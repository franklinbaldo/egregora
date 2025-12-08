"""CLI commands for viewing and managing pipeline run history."""

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import duckdb
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


class _RunsDuckDBStorage:
    """Minimal DuckDB storage used by the runs CLI without initializing Ibis."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = duckdb.connect(str(db_path))

    @contextlib.contextmanager
    def connection(self) -> contextlib.AbstractContextManager[duckdb.DuckDBPyConnection]:
        yield self._conn

    def execute_query(self, sql: str, params: list | None = None) -> list[tuple]:
        return self._conn.execute(sql, params or []).fetchall()

    def execute_query_single(self, sql: str, params: list | None = None) -> tuple | None:
        return self._conn.execute(sql, params or []).fetchone()

    def get_table_columns(self, table_name: str) -> set[str]:
        info = self._conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        return {row[1] for row in info}


def get_storage(db_path: Path) -> DuckDBStorageManager:
    """Get a DuckDBStorageManager instance."""
    return _RunsDuckDBStorage(db_path)


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


@dataclass
class RunDisplayData:
    """Structured data for run display."""

    run_id: str
    tenant_id: str | None
    stage: str
    status: str
    error: str | None
    parent_run_id: str | None
    code_ref: str | None
    config_hash: str | None
    started_at: str
    finished_at: str | None
    duration_seconds: float | None
    rows_in: int | None
    rows_out: int | None
    llm_calls: int
    tokens: int
    attrs: dict | None
    trace_id: str | None


def _format_metrics_section(data: RunDisplayData) -> list[str]:
    lines = []
    if (
        data.rows_in is not None
        or data.rows_out is not None
        or data.llm_calls
        or data.tokens
    ):
        lines.append("[bold]Metrics:[/bold]")
        if data.rows_in is not None:
            lines.append(f"  Rows In:   {data.rows_in:,}")
        if data.rows_out is not None:
            lines.append(f"  Rows Out:  {data.rows_out:,}")
        if data.llm_calls:
            lines.append(f"  LLM Calls: {data.llm_calls:,}")
        if data.tokens:
            lines.append(f"  Tokens:    {data.tokens:,}")
        lines.append("")
    return lines


def _format_tracking_section(data: RunDisplayData) -> list[str]:
    lines = []
    if data.parent_run_id or data.code_ref or data.config_hash:
        lines.append("[bold]Tracking:[/bold]")
        if data.parent_run_id:
            lines.append(f"  Parent: {data.parent_run_id}")
        if data.code_ref:
            lines.append(f"  Code:   {data.code_ref}")
        if data.config_hash:
            lines.append(f"  Config: {data.config_hash[:32]}...")
        lines.append("")
    return lines


def _build_run_panel_content(data: RunDisplayData) -> str:
    """Build formatted panel content from run data."""
    lines = []
    status_display = _format_status(data.status)
    lines.append(f"[bold cyan]Run ID:[/bold cyan] {data.run_id}")
    if data.tenant_id:
        lines.append(f"[bold cyan]Tenant:[/bold cyan] {data.tenant_id}")
    lines.append(f"[bold cyan]Stage:[/bold cyan] {data.stage}")
    lines.append(f"[bold cyan]Status:[/bold cyan] {status_display}")
    lines.append("")
    lines.append("[bold]Timestamps:[/bold]")
    lines.append(f"  Started:  {data.started_at}")
    if data.finished_at:
        lines.append(f"  Finished: {data.finished_at}")
    if data.duration_seconds:
        lines.append(f"  Duration: {data.duration_seconds:.2f}s")
    lines.append("")

    lines.extend(_format_metrics_section(data))
    lines.extend(_format_tracking_section(data))

    if data.error:
        lines.append("[bold red]Error:[/bold red]")
        lines.append(f"  {data.error}")
        lines.append("")
    if data.trace_id:
        lines.append("[bold]Observability:[/bold]")
        lines.append(f"  Trace ID: {data.trace_id}")
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

            # Unpack result (DuckDB fetchone returns tuple)
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

            display_data = RunDisplayData(
                run_id=run_id_full,
                tenant_id=tenant_id,
                stage=stage,
                status=status,
                error=error,
                parent_run_id=parent_run_id,
                code_ref=code_ref,
                config_hash=config_hash,
                started_at=str(started_at),
                finished_at=str(finished_at) if finished_at else None,
                duration_seconds=duration_seconds,
                rows_in=rows_in,
                rows_out=rows_out,
                llm_calls=llm_calls,
                tokens=tokens,
                attrs=attrs,
                trace_id=trace_id,
            )
            panel_content = _build_run_panel_content(display_data)
            panel = Panel(panel_content, title=f"[bold]Run Details: {stage}[/bold]", border_style="cyan")
            console.print(panel)
    except FileNotFoundError as exc:
        console.print(f"[red]No runs database found at {db_path}[/red]")
        raise typer.Exit(1) from exc
