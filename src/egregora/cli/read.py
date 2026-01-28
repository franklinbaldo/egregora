"""CLI commands for reader agent (post evaluation and ranking)."""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from egregora.agents.reader.models import RankingResult
from egregora.agents.reader.reader_runner import run_reader_evaluation
from egregora.config import load_egregora_config
from egregora.output_sinks.mkdocs import MkDocsPaths

logger = logging.getLogger(__name__)
console = Console()

read_app = typer.Typer(
    name="read",
    help="Evaluate and rank blog posts using reader agent",
    invoke_without_command=True,
    no_args_is_help=True,
)


@read_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    site_root: Annotated[
        Path | None,
        typer.Argument(help="Site root directory containing .egregora.toml"),
    ] = None,
    site: Annotated[
        str | None,
        typer.Option(
            "--site",
            help="Site identifier to use from the multi-site configuration",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Model override for reader agent (default: gemini-2.0-flash-exp)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Show top N posts in rankings (default: 10)",
        ),
    ] = 10,
) -> None:
    """Run reader agent evaluation and display post rankings.

    The reader agent performs pairwise comparisons of blog posts,
    updating ELO ratings based on quality judgments.

    Examples:
        egregora read my-blog/
        egregora read my-blog/ --limit 20
        egregora read my-blog/ --model google-gla:gemini-2.0-flash-exp

    """
    # If a subcommand is being invoked, don't run this callback
    if ctx.invoked_subcommand is not None:
        return

    # Require site_root when invoked directly
    if site_root is None:
        console.print("[red]Error: SITE_ROOT is required[/red]")
        raise typer.Exit(1)

    site_root = site_root.expanduser().resolve()

    # Verify .egregora directory exists
    egregora_dir = site_root / ".egregora"
    if not egregora_dir.exists():
        console.print(f"[red]No .egregora directory found in {site_root}[/red]")
        console.print("Run 'egregora init' or 'egregora write' first to create a site")
        raise typer.Exit(1)

    # Load configuration
    config = load_egregora_config(site_root, site=site)

    if not config.reader.enabled:
        console.print("[yellow]Reader agent is disabled in config[/yellow]")
        console.print("Set reader.enabled = true in .egregora.toml to enable")
        raise typer.Exit(0)

    # Get posts directory from config using standard resolution logic
    paths = MkDocsPaths(site_root, config=config)
    posts_dir = paths.posts_dir

    if not posts_dir.exists():
        console.print(f"[red]Posts directory not found: {posts_dir}[/red]")
        console.print(f"Expected posts in: {config.paths.posts_dir}")
        raise typer.Exit(1)

    console.print(f"[bold]Site root:[/bold] {site_root}")
    console.print(f"[bold]Evaluating posts in:[/bold] {posts_dir}")
    console.print(f"[bold]Comparisons per post:[/bold] {config.reader.comparisons_per_post}")
    console.print(f"[bold]ELO K-factor:[/bold] {config.reader.k_factor}\n")

    # Run evaluation
    try:
        rankings: list[RankingResult] = run_reader_evaluation(
            posts_dir=posts_dir,
            config=config.reader,
            model=model,
        )
    except Exception as e:
        console.print(f"[red]Error during evaluation: {e}[/red]")
        logger.exception("Reader evaluation failed")
        raise typer.Exit(1) from e

    if not rankings:
        console.print("[yellow]No rankings generated[/yellow]")
        raise typer.Exit(0)

    # Display results
    table = Table(title="📊 Post Quality Rankings")
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Post", style="green")
    table.add_column("ELO Rating", style="magenta", justify="right")
    table.add_column("Comparisons", justify="right")
    table.add_column("Win Rate", justify="right")

    for result in rankings[:limit]:
        table.add_row(
            str(result.rank),
            result.post_slug,
            f"{result.rating:.0f}",
            str(result.comparisons),
            f"{result.win_rate:.1f}%",
        )

    console.print(table)
    console.print(f"\n[dim]Showing top {min(limit, len(rankings))} of {len(rankings)} posts[/dim]")

    # Show database location
    db_path = site_root / config.reader.database_path
    console.print(f"[dim]Ratings stored in: {db_path}[/dim]")
