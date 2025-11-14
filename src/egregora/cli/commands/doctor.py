"""Diagnostic command for the CLI."""
from __future__ import annotations

from typing import Annotated

import typer

from egregora.cli import app, console
from egregora.diagnostics import HealthStatus, run_diagnostics


@app.command(name="doctor")
def doctor(
    *,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed diagnostic information")
    ] = False,
) -> None:
    """Run diagnostic checks to verify Egregora setup."""
    console.print("[bold cyan]Running diagnostics...[/bold cyan]")
    console.print()

    results = run_diagnostics()

    ok_count = sum(1 for r in results if r.status == HealthStatus.OK)
    warning_count = sum(1 for r in results if r.status == HealthStatus.WARNING)
    error_count = sum(1 for r in results if r.status == HealthStatus.ERROR)

    for result in results:
        if result.status == HealthStatus.OK:
            icon = "✅"
            color = "green"
        elif result.status == HealthStatus.WARNING:
            icon = "⚠️"
            color = "yellow"
        elif result.status == HealthStatus.ERROR:
            icon = "❌"
            color = "red"
        else:
            icon = "ℹ️"
            color = "cyan"

        console.print(f"[{color}]{icon} {result.check}:[/{color}] {result.message}")

        if verbose and result.details:
            for key, value in result.details.items():
                console.print(f"    {key}: {value}", style="dim")

    console.print()
    if error_count == 0 and warning_count == 0:
        console.print("[bold green]✅ All checks passed! Egregora is ready to use.[/bold green]")
    elif error_count == 0:
        console.print(
            f"[bold yellow]⚠️  {warning_count} warning(s) found. Egregora should work but some features may be limited.[/bold yellow]"
        )
    else:
        console.print(
            f"[bold red]❌ {error_count} error(s) found. Please fix these issues before using Egregora.[/bold red]"
        )

    console.print()
    console.print(f"[dim]Summary: {ok_count} OK, {warning_count} warnings, {error_count} errors[/dim]")

    if error_count > 0:
        raise typer.Exit(1)
