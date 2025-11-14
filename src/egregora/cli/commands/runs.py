"""Run history management commands."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from egregora.cli import app, console

runs_app = typer.Typer(
    name="runs",
    help="View and manage pipeline run history",
)
app.add_typer(runs_app)


@runs_app.command(name="tail")
def runs_tail(
    n: Annotated[int, typer.Option(help="Number of runs to show")] = 10,
    db_path: Annotated[Path, typer.Option(help="Runs database path")]
    = Path(".egregora-cache/runs.duckdb"),
) -> None:
    """Show last N runs."""
    import duckdb

    from rich.table import Table

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
                status_text = f"[green]{status}[/green]"
            elif status == "failed":
                status_text = f"[red]{status}[/red]"
            elif status == "running":
                status_text = f"[yellow]{status}[/yellow]"
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
    """Return color-coded status string."""
    if status == "completed":
        return f"[green]{status}[/green]"
    if status == "failed":
        return f"[red]{status}[/red]"
    if status == "running":
        return f"[yellow]{status}[/yellow]"
    return status


def _format_run_header(
    lines: list[str], run_id: str, tenant_id: str | None, stage: str, status_display: str
) -> None:
    """Append run header section to lines."""
    lines.append(f"[bold cyan]Run ID:[/bold cyan] {run_id}")
    if tenant_id:
        lines.append(f"[bold cyan]Tenant:[/bold cyan] {tenant_id}")
    lines.append(f"[bold cyan]Stage:[/bold cyan] {stage}")
    lines.append(f"[bold cyan]Status:[/bold cyan] {status_display}")
    lines.append("")


def _format_timestamps(
    lines: list[str], started_at: str, finished_at: str | None, duration_seconds: float | None
) -> None:
    """Append timestamps section to lines."""
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
    """Append metrics section to lines if any metrics exist."""
    if not (rows_in is not None or rows_out is not None or llm_calls or tokens):
        return
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


def _format_fingerprints(
    lines: list[str], input_fingerprint: str | None, code_ref: str | None, config_hash: str | None
) -> None:
    """Append fingerprints section to lines if any fingerprints exist."""
    if not (input_fingerprint or code_ref or config_hash):
        return
    lines.append("[bold]Fingerprints:[/bold]")
    if input_fingerprint:
        lines.append(f"  Input:  {input_fingerprint[:32]}...")
    if code_ref:
        lines.append(f"  Code:   {code_ref}")
    if config_hash:
        lines.append(f"  Config: {config_hash[:32]}...")
    lines.append("")


def _format_error(lines: list[str], error: str | None) -> None:
    """Append error section to lines if error exists."""
    if not error:
        return
    lines.append("[bold red]Error:[/bold red]")
    lines.append(f"  {error}")
    lines.append("")


def _format_observability(lines: list[str], trace_id: str | None) -> None:
    """Append observability section to lines if trace_id exists."""
    if not trace_id:
        return
    lines.append("[bold]Observability:[/bold]")
    lines.append(f"  Trace ID: {trace_id}")


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
    """Build formatted panel content from run data."""
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
    db_path: Annotated[Path, typer.Option(help="Runs database path")]
    = Path(".egregora-cache/runs.duckdb"),
) -> None:
    """Show detailed run info."""
    import duckdb

    from rich.panel import Panel

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
