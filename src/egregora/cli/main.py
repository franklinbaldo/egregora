"""Main Typer application for Egregora."""

import logging
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from egregora.cli.read import read_app
from egregora.cli.runs import get_storage, runs_app
from egregora.config import RuntimeContext, load_egregora_config
from egregora.config.config_validation import parse_date_arg, validate_retrieval_config, validate_timezone
from egregora.constants import RetrievalMode, SourceType, WindowUnit
from egregora.database.elo_store import EloStore
from egregora.init import ensure_mkdocs_project
from egregora.orchestration import write_pipeline

app = typer.Typer(
    name="egregora",
    help="Ultra-simple WhatsApp to blog pipeline with LLM-powered content generation",
    add_completion=False,
)
app.add_typer(runs_app)
app.add_typer(read_app)

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
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)

logger = logging.getLogger(__name__)


@app.callback()
def main() -> None:
    """Initialize CLI (placeholder for future setup)."""


def _ensure_mkdocs_scaffold(output_dir: Path) -> None:
    """Ensure site is initialized, creating if needed with user confirmation."""
    config_path = output_dir / ".egregora" / "config.yml"
    if config_path.exists():
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    warning_message = (
        f"[yellow]Warning:[/yellow] Egregora site not initialized in {output_dir}. "
        "Egregora can initialize a new site before processing."
    )
    console.print(warning_message)

    proceed = True
    if any(output_dir.iterdir()):
        proceed = typer.confirm(
            "The output directory is not empty and lacks .egregora/config.yml. Initialize a fresh site here?",
            default=False,
        )

    if not proceed:
        console.print("[red]Aborting processing at user's request.[/red]")
        raise typer.Exit(1)

    logger.info("Initializing site in %s", output_dir)
    ensure_mkdocs_project(output_dir)
    console.print("[green]Initialized site. Continuing with processing.[/green]")


@app.command()
def init(
    output_dir: Annotated[Path, typer.Argument(help="Directory path for the new site (e.g., 'my-blog')")],
    interactive: Annotated[  # noqa: FBT002
        bool,
        typer.Option(
            "--interactive/--no-interactive",
            "-i",
            help="Prompt for site settings (auto-disabled in non-TTY environments)",
        ),
    ] = True,
) -> None:
    """Initialize a new MkDocs site scaffold for serving Egregora posts."""
    import sys

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

    docs_dir, mkdocs_created = ensure_mkdocs_project(site_root, site_name=site_name)
    if mkdocs_created:
        console.print(
            Panel(
                f"[bold green]✅ MkDocs site scaffold initialized successfully![/bold green]\n\n📁 Site root: {site_root}\n📝 Docs directory: {docs_dir}\n\n[bold]Next steps:[/bold]\n• Install MkDocs: [cyan]pip install 'mkdocs-material[imaging]'[/cyan]\n• Change to site directory: [cyan]cd {output_dir}[/cyan]\n• Serve the site: [cyan]mkdocs serve[/cyan]\n• Process WhatsApp export: [cyan]egregora process export.zip --output={output_dir}[/cyan]",
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


@app.command()
def write(  # noqa: C901, PLR0913
    input_file: Annotated[Path, typer.Argument(help="Path to chat export file (ZIP, JSON, etc.)")],
    *,
    source: Annotated[
        SourceType,
        typer.Option(help="Source type (whatsapp, iperon-tjro, self)", case_sensitive=False),
    ] = SourceType.WHATSAPP,
    output: Annotated[Path, typer.Option(help="Output directory for generated site")] = Path("output"),
    step_size: Annotated[int, typer.Option(help="Size of each processing window")] = 1,
    step_unit: Annotated[
        WindowUnit,
        typer.Option(help="Unit for windowing", case_sensitive=False),
    ] = WindowUnit.DAYS,
    overlap: Annotated[
        float, typer.Option(help="Overlap ratio between windows (0.0-0.5, default 0.2 = 20%)")
    ] = 0.2,
    enable_enrichment: Annotated[bool, typer.Option(help="Enable LLM enrichment for URLs/media")] = True,
    from_date: Annotated[
        str | None, typer.Option(help="Only process messages from this date onwards (YYYY-MM-DD)")
    ] = None,
    to_date: Annotated[
        str | None, typer.Option(help="Only process messages up to this date (YYYY-MM-DD)")
    ] = None,
    timezone: Annotated[
        str | None, typer.Option(help="Timezone for date parsing (e.g., 'America/New_York')")
    ] = None,
    model: Annotated[
        str | None, typer.Option(help="Gemini model to use (or configure in mkdocs.yml)")
    ] = None,
    retrieval_mode: Annotated[
        RetrievalMode,
        typer.Option(help="Retrieval strategy: ann (default) or exact", case_sensitive=False),
    ] = RetrievalMode.ANN,
    retrieval_nprobe: Annotated[
        int | None, typer.Option(help="Advanced: override DuckDB VSS nprobe for ANN retrieval")
    ] = None,
    retrieval_overfetch: Annotated[
        int | None, typer.Option(help="Advanced: multiply ANN candidate pool before filtering")
    ] = None,
    max_prompt_tokens: Annotated[
        int, typer.Option(help="Maximum tokens per prompt (default 100k cap, prevents overflow)")
    ] = 100_000,
    use_full_context_window: Annotated[
        bool, typer.Option(help="Use full model context window (overrides --max-prompt-tokens)")
    ] = False,
    max_windows: Annotated[
        int | None,
        typer.Option(help="Maximum number of windows to process (default: 1, use 0 for all windows)"),
    ] = 1,
    resume: Annotated[
        bool,
        typer.Option(
            help="Enable incremental processing (resume from checkpoint). Default: always rebuild from scratch."
        ),
    ] = False,
    refresh: Annotated[
        str | None,
        typer.Option(
            help="Comma-separated cache tiers to invalidate (e.g., 'writer', 'rag', 'enrichment', 'all').",
        ),
    ] = None,
    debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
) -> None:
    """Write blog posts from chat exports using LLM-powered synthesis.

    Supports multiple sources (WhatsApp, Slack, etc.) via the --source flag.

    Windowing:
        Control how messages are grouped into posts using --step-size and --step-unit:

        By time (default):
            egregora write export.zip --step-size=1 --step-unit=days
            egregora write export.zip --step-size=7 --step-unit=days
            egregora write export.zip --step-size=24 --step-unit=hours

        By message count:
            egregora write export.zip --step-size=100 --step-unit=messages

    The LLM decides:
    - What's worth writing about (filters noise automatically)
    - How many posts per window (0-N)
    - All metadata (title, slug, tags, summary, etc)
    - Which author profiles to update based on contributions
    """
    # Setup debug logging
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse and validate date arguments
    from_date_obj: date | None = None
    to_date_obj: date | None = None
    if from_date:
        try:
            from_date_obj = parse_date_arg(from_date, "from_date")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e
    if to_date:
        try:
            to_date_obj = parse_date_arg(to_date, "to_date")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e

    # Validate timezone
    if timezone:
        try:
            validate_timezone(timezone)
            console.print(f"[green]Using timezone: {timezone}[/green]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e

    # Validate retrieval config
    try:
        retrieval_mode_str = validate_retrieval_config(
            retrieval_mode.value, retrieval_nprobe, retrieval_overfetch
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    # Resolve paths
    output_dir = output.expanduser().resolve()
    _ensure_mkdocs_scaffold(output_dir)

    # Load base config and merge CLI overrides
    base_config = load_egregora_config(output_dir)
    models_update: dict[str, str] = {}
    if model:
        models_update = {
            "writer": model,
            "enricher": model,
            "enricher_vision": model,
            "ranking": model,
            "editor": model,
        }
    egregora_config = base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "step_size": step_size,
                    "step_unit": step_unit,
                    "overlap_ratio": overlap,
                    "timezone": timezone,
                    "from_date": from_date_obj.isoformat() if from_date_obj else None,
                    "to_date": to_date_obj.isoformat() if to_date_obj else None,
                    "max_prompt_tokens": max_prompt_tokens,
                    "use_full_context_window": use_full_context_window,
                    "max_windows": max_windows,
                    "checkpoint_enabled": resume,
                }
            ),
            "enrichment": base_config.enrichment.model_copy(update={"enabled": enable_enrichment}),
            "rag": base_config.rag.model_copy(
                update={
                    "mode": retrieval_mode_str,
                    "nprobe": retrieval_nprobe if retrieval_nprobe is not None else base_config.rag.nprobe,
                    "overfetch": retrieval_overfetch
                    if retrieval_overfetch is not None
                    else base_config.rag.overfetch,
                }
            ),
            **({"models": base_config.models.model_copy(update=models_update)} if models_update else {}),
        },
    )

    # Create runtime context
    runtime = RuntimeContext(
        output_dir=output_dir,
        input_file=input_file,
        model_override=model,
        debug=debug,
    )

    # Run pipeline
    try:
        console.print(
            Panel(
                f"[cyan]Source:[/cyan] {source.value}\n[cyan]Input:[/cyan] {input_file}\n[cyan]Output:[/cyan] {output_dir}\n[cyan]Windowing:[/cyan] {step_size} {step_unit.value}",
                title="⚙️  Egregora Pipeline",
                border_style="cyan",
            )
        )
        write_pipeline.run(
            source=source.value,
            input_path=runtime.input_file,
            output_dir=runtime.output_dir,
            config=egregora_config,
            refresh=refresh,
        )
        console.print("[green]Processing completed successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Pipeline failed: {e}[/red]")
        if debug:
            raise
        raise typer.Exit(1) from e


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
    from rich.table import Table

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

    storage = get_storage(db_path)
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
    from rich.table import Table

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

    storage = get_storage(db_path)
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
    from egregora.diagnostics import HealthStatus, run_diagnostics

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
            icon = "ℹ️"  # noqa: RUF001
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
