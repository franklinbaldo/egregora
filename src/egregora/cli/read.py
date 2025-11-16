"""CLI commands for reader agent (post evaluation and ranking)."""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from egregora.agents.reader.reader_runner import run_reader_evaluation
from egregora.config import load_egregora_config

logger = logging.getLogger(__name__)
console = Console()

read_app = typer.Typer(
    name="read",
    help="Evaluate and rank blog posts using reader agent",
)


@read_app.command(name="rank")
def rank_posts(
    site_root: Annotated[
        Path,
        typer.Argument(help="Site root directory containing .egregora/config.yml"),
    ],
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
        egregora read rank my-blog/
        egregora read rank my-blog/ --limit 20
        egregora read rank my-blog/ --model google-gla:gemini-2.0-flash-thinking-exp
    """
    site_root = site_root.expanduser().resolve()

    # Verify .egregora directory exists
    egregora_dir = site_root / ".egregora"
    if not egregora_dir.exists():
        console.print(f"[red]No .egregora directory found in {site_root}[/red]")
        console.print("Run 'egregora init' or 'egregora write' first to create a site")
        raise typer.Exit(1)

    # Load configuration
    config = load_egregora_config(site_root)

    if not config.reader.enabled:
        console.print("[yellow]Reader agent is disabled in config[/yellow]")
        console.print("Set reader.enabled = true in .egregora/config.yml to enable")
        raise typer.Exit(0)

    # Get posts directory from config
    posts_dir = site_root / config.paths.posts_dir

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
        rankings = asyncio.run(
            run_reader_evaluation(
                posts_dir=posts_dir,
                config=config.reader,
                model=model,
            )
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


@read_app.command(name="history")
def show_history(
    site_root: Annotated[
        Path,
        typer.Argument(help="Site root directory containing .egregora/config.yml"),
    ],
    post_slug: Annotated[
        str | None,
        typer.Option(
            "--post",
            "-p",
            help="Show comparisons for specific post",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Number of comparisons to show",
        ),
    ] = 20,
) -> None:
    """Show comparison history from reader agent.

    Examples:
        egregora read history my-blog/
        egregora read history my-blog/ --post my-post-slug
        egregora read history my-blog/ --limit 50
    """
    from egregora.database.elo_store import EloStore

    site_root = site_root.expanduser().resolve()

    # Verify .egregora directory exists
    egregora_dir = site_root / ".egregora"
    if not egregora_dir.exists():
        console.print(f"[red]No .egregora directory found in {site_root}[/red]")
        console.print("Run 'egregora init' or 'egregora write' first to create a site")
        raise typer.Exit(1)

    config = load_egregora_config(site_root)

    db_path = site_root / config.reader.database_path

    if not db_path.exists():
        console.print(f"[red]Reader database not found: {db_path}[/red]")
        console.print("Run 'egregora read rank' first to generate rankings")
        raise typer.Exit(1)

    elo_store = EloStore(db_path)

    try:
        history = elo_store.get_comparison_history(
            post_slug=post_slug,
            limit=limit,
        ).execute()

        if history.empty:
            console.print("[yellow]No comparison history found[/yellow]")
            return

        table = Table(title=f"🔍 Comparison History{f' for {post_slug}' if post_slug else ''}")
        table.add_column("Timestamp", style="dim")
        table.add_column("Post A", style="cyan")
        table.add_column("Post B", style="cyan")
        table.add_column("Winner", style="green", justify="center")
        table.add_column("Rating Changes", style="magenta")

        for row in history.itertuples(index=False):
            winner_emoji = {"a": "🅰️", "b": "🅱️", "tie": "🤝"}[row.winner]

            rating_change_a = row.rating_a_after - row.rating_a_before
            rating_change_b = row.rating_b_after - row.rating_b_before

            table.add_row(
                str(row.timestamp)[:19],
                row.post_a_slug,
                row.post_b_slug,
                winner_emoji,
                f"A: {rating_change_a:+.0f} / B: {rating_change_b:+.0f}",
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(history)} comparison(s)[/dim]")

    finally:
        elo_store.close()
