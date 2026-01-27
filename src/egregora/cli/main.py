"""Main Typer application for Egregora."""

import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

try:
    import dotenv
except ImportError:
    dotenv = None

# Deferred import if needed, but for now moving it top level as requested by linter
# We need to make sure this doesn't break things if import fails, but diagnostics is part of the package.
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from egregora.cli.diagnostics import HealthStatus, run_diagnostics

# from egregora.cli.db import db_app  # Removed - db.py no longer exists
from egregora.cli.read import read_app
from egregora.config import load_egregora_config
from egregora.config.exceptions import ApiKeyNotFoundError
from egregora.constants import SourceType, WindowUnit
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.elo_store import EloStore
<<<<<<< HEAD
from egregora.llm.api_keys import get_google_api_key
=======
>>>>>>> origin/pr/2736
from egregora.orchestration.pipelines.write import run_cli_flow
from egregora.output_adapters.mkdocs.paths import MkDocsPaths
from egregora.output_adapters.mkdocs.scaffolding import MkDocsSiteScaffolder

app = typer.Typer(
    name="egregora",
    help="Ultra-simple WhatsApp to blog pipeline with LLM-powered content generation",
    add_completion=False,
)
app.add_typer(read_app)

# Database subcommands
# app.add_typer(db_app)  # Removed - db.py no longer exists

# Show subcommands
show_app = typer.Typer(
    name="show",
    help="Display information about site components",
)
app.add_typer(show_app)

# Simple logging setup (no telemetry)
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        RichHandler(
            console=console,
            rich_tracebacks=True,
            show_path=False,
            log_time_format="[%Y-%m-%d %H:%M:%S]",  # ISO date format
        )
    ],
)

logger = logging.getLogger(__name__)


@app.callback()
def main() -> None:
    """Initialize CLI (placeholder for future setup)."""


@app.command()
def init(
    output_dir: Annotated[Path, typer.Argument(help="Directory path for the new site (e.g., 'my-blog')")],
    *,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive/--no-interactive",
            "-i",
            help="Prompt for site settings (disabled by default)",
        ),
    ] = False,
) -> None:
    """Initialize a new MkDocs site scaffold for serving Egregora posts."""
    site_root = output_dir.resolve()

    # Auto-disable interactive mode if not in a TTY (e.g., CI/CD)
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    interactive = interactive and is_tty

    # Interactive prompts for better UX
    site_name = None
    if interactive:
        console.print("\n[bold cyan]🛠️  Egregora Site Initialization[/bold cyan]\n")
        site_name = typer.prompt(
            "Site name",
            default=site_root.name or "Egregora Archive",
        )
    else:
        site_name = site_root.name or "Egregora Archive"

    scaffolder = MkDocsSiteScaffolder()
    _, mkdocs_created = scaffolder.scaffold_site(site_root, site_name=site_name)
    docs_dir = MkDocsPaths(site_root).docs_dir
    if mkdocs_created:
        console.print(
            Panel(
                f"[bold green]✅ MkDocs site scaffold initialized successfully![/bold green]\n\n"
                f"📁 Site root: {site_root}\n"
                f"📝 Docs directory: {docs_dir}\n\n"
                f"[bold]Next steps:[/bold]\n"
                f"1. Generate content:\n   [cyan]egregora write path/to/chat_export.zip --output-dir {output_dir}[/cyan]\n"
                f'2. Preview the site:\n   [cyan]cd {output_dir}[/cyan]\n   [cyan]uv tool run --with "mkdocs-material\\[imaging]" --with pillow --with cairosvg --with mkdocs-blogging-plugin --with mkdocs-macros-plugin --with mkdocs-rss-plugin --with mkdocs-glightbox --with mkdocs-git-revision-date-localized-plugin --with mkdocs-minify-plugin mkdocs serve -f .egregora/mkdocs.yml[/cyan]',
                title="🛠️ Initialization Complete",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold yellow]⚠️ MkDocs site already exists at {site_root}[/bold yellow]\n\n📁 Using existing setup:\n• Docs directory: {docs_dir}\n\n[bold]To update or regenerate:[/bold]\n• Manually edit [cyan]mkdocs.yml[/cyan] or remove it to reinitialize.",
                title="📁 Site Exists",
                border_style="yellow",
            )
        )


# TODO: [Taskmaster] Refactor the write command to use a Pydantic model for its parameters.
@app.command()
def write(
    input_file: Annotated[Path, typer.Argument(help="Path to chat export file (ZIP, JSON, etc.)")],
    *,
    output: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Directory for the generated site")
    ] = Path("site"),
    source: Annotated[
        SourceType, typer.Option("--source-type", "-s", help="Source format of the input")
    ] = SourceType.WHATSAPP,
    step_size: Annotated[int, typer.Option(help="Window size (messages or hours)")] = 100,
    step_unit: Annotated[WindowUnit, typer.Option(help="Unit for windowing")] = WindowUnit.MESSAGES,
    overlap: Annotated[float, typer.Option(help="Overlap ratio between windows (0.0-1.0)")] = 0.0,
    enable_enrichment: Annotated[
        bool,
        typer.Option(
            "--enable-enrichment/--no-enable-enrichment",
            help="Enable AI enrichment (images, links)",
        ),
    ] = True,
    from_date: Annotated[str | None, typer.Option(help="Start date filter (YYYY-MM-DD)")] = None,
    to_date: Annotated[str | None, typer.Option(help="End date filter (YYYY-MM-DD)")] = None,
    timezone: Annotated[str | None, typer.Option(help="Timezone for date calculations")] = None,
    model: Annotated[str | None, typer.Option(help="Override LLM model for all tasks")] = None,
    max_prompt_tokens: Annotated[int, typer.Option(help="Maximum context window size")] = 400000,
    use_full_context_window: Annotated[
        bool, typer.Option("--full-context", help="Use maximum available context")
    ] = False,
    max_windows: Annotated[int | None, typer.Option(help="Limit number of windows to process")] = None,
    resume: Annotated[
        bool,
        typer.Option("--resume/--no-resume", help="Resume from last checkpoint if available"),
    ] = True,
    refresh: Annotated[
        str | None,
        typer.Option(help="Force refresh components (writer, rag, enrichment, all)"),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force full refresh (same as --refresh all)")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable debug logging")] = False,
    options: Annotated[
        str | None,
        typer.Option(
            "--options",
            help="JSON string of write options; if provided, overrides CLI defaults",
        ),
    ] = None,
) -> None:
    """Write blog posts from chat exports using LLM-powered synthesis."""
    run_cli_flow(
        input_file=input_file,
        output=output,
        source=source,
        step_size=step_size,
        step_unit=step_unit,
        overlap=overlap,
        enable_enrichment=enable_enrichment,
        from_date=from_date,
        to_date=to_date,
        timezone=timezone,
        model=model,
        max_prompt_tokens=max_prompt_tokens,
        use_full_context_window=use_full_context_window,
        max_windows=max_windows,
        resume=resume,
        refresh=refresh,
        force=force,
        debug=debug,
        options=options,
    )


# TODO: [Taskmaster] Refactor site validation logic into a reusable utility function.
@app.command()
def top(
    site_root: Annotated[
        Path,
        typer.Argument(help="Site root directory containing .egregora/config.yml"),
    ],
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Number of top posts to show (default: 10)",
        ),
    ] = 10,
) -> None:
    """Show top-ranked posts without running evaluation.

    Displays existing rankings from the reader agent database.

    Examples:
        egregora top my-blog/
        egregora top my-blog/ --limit 20

    """
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
        console.print("Run 'egregora read' first to generate rankings")
        raise typer.Exit(1)

    # Use DuckDBStorageManager directly to ensure Ibis compatibility with EloStore
    storage = DuckDBStorageManager(db_path)
    elo_store = EloStore(storage)

    top_posts = elo_store.get_top_posts(limit=limit).execute()

    if top_posts.empty:
        console.print("[yellow]No rankings found[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"🏆 Top {limit} Posts")
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Post", style="green")
    table.add_column("ELO Rating", style="magenta", justify="right")
    table.add_column("Comparisons", justify="right")
    table.add_column("Win Rate", justify="right")

    for rank, row in enumerate(top_posts.itertuples(index=False), 1):
        total_games = row.comparisons
        win_rate = (row.wins / total_games * 100) if total_games > 0 else 0.0

        table.add_row(
            str(rank),
            row.post_slug,
            f"{row.rating:.0f}",
            str(row.comparisons),
            f"{win_rate:.1f}%",
        )

    console.print(table)
    console.print(f"\n[dim]Database: {db_path}[/dim]")


@show_app.command(name="reader-history")
def show_reader_history(
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
        egregora show reader-history my-blog/
        egregora show reader-history my-blog/ --post my-post-slug
        egregora show reader-history my-blog/ --limit 50

    """
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
        console.print("Run 'egregora read' first to generate rankings")
        raise typer.Exit(1)

    # Use DuckDBStorageManager directly to ensure Ibis compatibility with EloStore
    storage = DuckDBStorageManager(db_path)
    elo_store = EloStore(storage)

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


@app.command(name="doctor")
def doctor(
    *,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed diagnostic information")
    ] = False,
) -> None:
    """Run diagnostic checks to verify Egregora setup."""
    _run_doctor_checks(verbose=verbose)


def _run_offline_demo(output_dir: Path) -> None:
    """Generate a placeholder demo site when no API key is available."""
    console.print("[bold cyan]Generating a placeholder demo site...[/bold cyan]")
    console.print(
        "[dim]This is a sample site with placeholder content. "
        "To generate a site from your own chat export, use the `egregora write` command.[/dim]"
    )

    # 1. Scaffold the site
    scaffolder = MkDocsSiteScaffolder()
    scaffolder.scaffold_site(output_dir, site_name="Egregora Demo (Offline)")

    # 2. Create a placeholder post
    posts_dir = output_dir / "docs" / "posts"
    posts_dir.mkdir(exist_ok=True, parents=True)
    post_content = """---
title: Welcome to Egregora!
date: 2025-01-01
---

# Welcome to Your Egregora Demo Site!

This is a placeholder post because the `egregora demo` command was run without a Google API key.

To generate a full demo with content synthesized from a sample chat, please:

1.  Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2.  Set the environment variable:
    ```bash
    export GEMINI_API_KEY="YOUR_API_KEY_HERE"
    ```
3.  Run the demo command again:
    ```bash
    egregora demo
    ```

This will replace this placeholder site with a fully-featured blog generated by the Egregora pipeline.
"""
    (posts_dir / "2025-01-01-welcome.md").write_text(post_content)

    # 3. Create a placeholder index
    index_content = "# Welcome to Egregora\n\nThis is a demo site. See the first post [here](./posts/2025-01-01-welcome.md)."
    (output_dir / "docs" / "index.md").write_text(index_content)


@app.command()
def demo(
    *,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="The directory to output the demo site to.",
        ),
    ] = Path("demo"),
    enable_enrichment: Annotated[
        bool,
        typer.Option(
            "--enable-enrichment/--no-enable-enrichment",
            help="Enable AI enrichment (images, links)",
        ),
    ] = True,
) -> None:
    """Generate a demo site from a sample WhatsApp export."""
    try:
        get_google_api_key()
        console.print(
            "[bold cyan]🚀 API key found. Generating full demo site with LLM content...[/bold cyan]"
        )

        from egregora.assets import get_demo_chat_path

        sample_input = get_demo_chat_path()
        if not sample_input.exists():
            console.print(f"[red]Sample input file not found at {sample_input}[/red]")
            raise typer.Exit(1)

        try:
            run_cli_flow(
                input_file=sample_input,
                output=output_dir,
                source=SourceType.WHATSAPP,
                step_size=100,
                step_unit=WindowUnit.MESSAGES,
                overlap=0.0,
                enable_enrichment=enable_enrichment,
                from_date=None,
                to_date=None,
                timezone=None,
                model=None,
                max_prompt_tokens=400000,
                use_full_context_window=False,
                max_windows=2,
                resume=True,
                refresh=None,
                force=True,  # Always force a refresh for the demo
                debug=False,
                options=None,
                exit_on_error=False,
            )
<<<<<<< HEAD
        except Exception as e:
=======
        except (AllModelsExhaustedError, RuntimeError) as e:
>>>>>>> origin/pr/2660
            console.print(f"[bold yellow]⚠️  Content generation failed: {e}[/bold yellow]")
            console.print(
                "[dim]The demo site scaffold has been created, but without AI-generated content.[/dim]"
            )
            # Ensure the scaffold exists even if run_cli_flow failed mid-process
            scaffolder = MkDocsSiteScaffolder()
            scaffolder.scaffold_site(output_dir, site_name="Egregora Demo (Content Failed)")

    except ApiKeyNotFoundError:
        _run_offline_demo(output_dir)

    # Final success message
    console.print(
        Panel(
            "[bold green]✅ Demo site generated successfully![/bold green]\n\n"
            "To view the site, run:\n"
            f'[cyan]cd {output_dir} && uv tool run --with "mkdocs-material\\[imaging]" --with pillow --with cairosvg --with mkdocs-blogging-plugin --with mkdocs-macros-plugin --with mkdocs-rss-plugin --with mkdocs-glightbox --with mkdocs-git-revision-date-localized-plugin --with mkdocs-minify-plugin mkdocs serve -f .egregora/mkdocs.yml[/cyan]',
            title="🚀 Demo Complete",
            border_style="green",
        )
    )


def _load_dotenv_if_available(output_dir: Path) -> None:
    if dotenv:
        dotenv.load_dotenv(output_dir / ".env")
        dotenv.load_dotenv()  # Check CWD as well


def _run_doctor_checks(*, verbose: bool) -> None:
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
            icon = "i"
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
