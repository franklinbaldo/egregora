"""Run tracking commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import duckdb
import typer
from rich.panel import Panel
from rich.table import Table

from egregora.cli._app import app, console

runs_app = typer.Typer(
    name="runs",
    help="View and manage pipeline run history",
)
app.add_typer(runs_app)


@runs_app.command(name="tail")
def runs_tail(
    n: Annotated[int, typer.Option(help="Number of runs to show")] = 10,
    db_path: Annotated[Path, typer.Option(help="Runs database path")] = Path(".egregora-cache/runs.duckdb"),
) -> None:
    """Show last N runs."""
    if not db_path.exists():
        console.print(f"[yellow]No runs database found at {db_path}[/yellow]")
        console.print("[dim]Runs will be tracked after first pipeline execution[/dim]")
        return

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        result = conn.execute(
            """
            WITH run_summary AS (
                SELECT
                    run_id,
                    stage,
                    LAST(status ORDER BY timestamp) as status,
                    MIN(CASE WHEN status = 'started' THEN timestamp END) as started_at,
                    MAX(CASE WHEN status = 'started' THEN rows_in END) as rows_in,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN rows_out END) as rows_out,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN duration_seconds END) as duration_seconds
                FROM run_events
                GROUP BY run_id, stage
            )
            SELECT *
            FROM run_summary
            WHERE started_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT ?
            """,
            [n],
        ).fetchall()

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

            if status == "completed":
                status_text = "[green]completed[/green]"
            elif status == "failed":
                status_text = "[red]failed[/red]"
            elif status == "running":
                status_text = "[yellow]running[/yellow]"
            else:
                status_text = status

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

    finally:
        conn.close()


def _format_status(status: str) -> str:
    if status == "completed":
        return "[green]completed[/green]"
    if status == "failed":
        return "[red]failed[/red]"
    if status == "running":
        return "[yellow]running[/yellow]"
    return status


def _format_run_header(
    lines: list[str], run_id: str, tenant_id: str | None, stage: str, status_display: str
) -> None:
    lines.append(f"[bold cyan]Run ID:[/bold cyan] {run_id}")
    if tenant_id:
        lines.append(f"[bold cyan]Tenant:[/bold cyan] {tenant_id}")
    lines.append(f"[bold cyan]Stage:[/bold cyan] {stage}")
    lines.append(f"[bold cyan]Status:[/bold cyan] {status_display}")
    lines.append("")


def _format_timestamps(
    lines: list[str], started_at: str, finished_at: str | None, duration_seconds: float | None
) -> None:
    lines.append("[bold]Timestamps:[/bold]")
    lines.append(f"  Started:  {started_at}")
    if finished_at:
        lines.append(f"  Finished: {finished_at}")
    if duration_seconds:
        lines.append(f"  Duration: {duration_seconds:.2f}s")
    lines.append("")


def _format_metrics(
    lines: list[str], rows_in: int | None, rows_out: int | None, llm_calls: int | None, tokens: int | None
) -> None:
    lines.append("[bold]Metrics:[/bold]")
    lines.append(f"  Rows in:  {rows_in if rows_in is not None else '-'}")
    lines.append(f"  Rows out: {rows_out if rows_out is not None else '-'}")
    lines.append(f"  LLM calls: {llm_calls if llm_calls is not None else '-'}")
    lines.append(f"  Tokens:    {tokens if tokens is not None else '-'}")
    lines.append("")


def _format_fingerprints(
    lines: list[str], input_fingerprint: str | None, code_ref: str | None, config_hash: str | None
) -> None:
    lines.append("[bold]Fingerprints:[/bold]")
    lines.append(f"  Input:  {input_fingerprint or '-'}")
    lines.append(f"  Code:   {code_ref or '-'}")
    lines.append(f"  Config: {config_hash or '-'}")
    lines.append("")


def _format_error(lines: list[str], error: str | None) -> None:
    if not error:
        return
    lines.append("[bold red]Error:[/bold red]")
    lines.append(f"  {error}")
    lines.append("")


def _format_observability(lines: list[str], trace_id: str | None) -> None:
    lines.append("[bold]Observability:[/bold]")
    lines.append(f"  Trace ID: {trace_id or '-'}")


def _build_run_panel_content(
    run_id: str,
    tenant_id: str | None,
    stage: str,
    status: str,
    error: str | None,
    input_fingerprint: str | None,
    code_ref: str | None,
    config_hash: str | None,
    started_at: str,
    finished_at: str | None,
    duration_seconds: float | None,
    rows_in: int | None,
    rows_out: int | None,
    llm_calls: int | None,
    tokens: int | None,
    trace_id: str | None,
) -> str:
    lines: list[str] = []
    status_display = _format_status(status)
    _format_run_header(lines, run_id, tenant_id, stage, status_display)
    _format_timestamps(lines, started_at, finished_at, duration_seconds)
    _format_metrics(lines, rows_in, rows_out, llm_calls, tokens)
    _format_fingerprints(lines, input_fingerprint, code_ref, config_hash)
    _format_error(lines, error)
    _format_observability(lines, trace_id)
    return "\n".join(lines)


@runs_app.command(name="show")
def runs_show(
    run_id: Annotated[str, typer.Argument(help="Run ID to show (full UUID or prefix)")],
    db_path: Annotated[Path, typer.Option(help="Runs database path")] = Path(".egregora-cache/runs.duckdb"),
) -> None:
    """Show detailed run info."""
    if not db_path.exists():
        console.print(f"[red]No runs database found at {db_path}[/red]")
        raise typer.Exit(1)

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        result = conn.execute(
            """
            WITH run_events_filtered AS (
                SELECT *
                FROM run_events
                WHERE CAST(run_id AS VARCHAR) LIKE ?
            ),
            run_summary AS (
                SELECT
                    run_id,
                    MAX(tenant_id) as tenant_id,
                    stage,
                    LAST(status ORDER BY timestamp) as status,
                    LAST(error ORDER BY timestamp) FILTER (WHERE error IS NOT NULL) as error,
                    MAX(CASE WHEN status = 'started' THEN input_fingerprint END) as input_fingerprint,
                    MAX(code_ref) as code_ref,
                    MAX(config_hash) as config_hash,
                    MIN(CASE WHEN status = 'started' THEN timestamp END) as started_at,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN timestamp END) as finished_at,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN duration_seconds END) as duration_seconds,
                    MAX(CASE WHEN status = 'started' THEN rows_in END) as rows_in,
                    MAX(CASE WHEN status IN ('completed', 'failed') THEN rows_out END) as rows_out,
                    MAX(llm_calls) as llm_calls,
                    MAX(tokens) as tokens,
                    MAX(trace_id) as trace_id
                FROM run_events_filtered
                GROUP BY run_id, stage
            )
            SELECT *
            FROM run_summary
            WHERE started_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 1
            """,
            [f"{run_id}%"],
        ).fetchone()

        if not result:
            console.print(f"[red]Run not found: {run_id}[/red]")
            raise typer.Exit(1)

        (
            run_id_full,
            tenant_id,
            stage,
            status,
            error,
            input_fingerprint,
            code_ref,
            config_hash,
            started_at,
            finished_at,
            duration_seconds,
            rows_in,
            rows_out,
            llm_calls,
            tokens,
            trace_id,
        ) = result

        panel_content = _build_run_panel_content(
            run_id_full,
            tenant_id,
            stage,
            status,
            error,
            input_fingerprint,
            code_ref,
            config_hash,
            started_at,
            finished_at,
            duration_seconds,
            rows_in,
            rows_out,
            llm_calls,
            tokens,
            trace_id,
        )

        panel = Panel(panel_content, title=f"[bold]Run Details: {stage}[/bold]", border_style="cyan")
        console.print(panel)

    finally:
        conn.close()
