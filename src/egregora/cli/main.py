"""Main Typer application for Egregora."""

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Any

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

from egregora.cli.read import read_app
# Moved get_storage locally to support top/history commands
import contextlib
import duckdb
from egregora.config import RuntimeContext, load_egregora_config
from egregora.config.config_validation import parse_date_arg, validate_timezone
from egregora.constants import SourceType, WindowUnit
from egregora.database.elo_store import EloStore
from egregora.diagnostics import HealthStatus, run_diagnostics
from egregora.init import ensure_mkdocs_project
from egregora.orchestration import write_pipeline
from egregora.orchestration.context import PipelineRunParams
from egregora.utils.env import validate_gemini_api_key


# MOVED from runs.py to support top/history commands
class _RunsDuckDBStorage:
    """Minimal DuckDB storage used by CLI commands without initializing Ibis."""

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


def get_storage(db_path: Path):
    """Get a DuckDBStorageManager instance."""
    return _RunsDuckDBStorage(db_path)


app = typer.Typer(
    name="egregora",
    help="Ultra-simple WhatsApp to blog pipeline with LLM-powered content generation",
    add_completion=False,
)
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


def _ensure_mkdocs_scaffold(output_dir: Path) -> None:
    """Ensure site is initialized, creating if needed with user confirmation."""
    config_path = output_dir / ".egregora" / "config.yml"
    config_path_alt = output_dir / ".egregora" / "config.yaml"
    if config_path.exists() or config_path_alt.exists():
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


def _resolve_gemini_key() -> str | None:
    """Resolve Google Gemini API key from environment."""
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


@app.command()
def init(
    output_dir: Annotated[
        Path, typer.Argument(help="Directory path for the new site (e.g., 'my-blog')")
    ],
    *,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive/--no-interactive",
            "-i",
            help="Prompt for site settings (auto-disabled in non-TTY environments)",
        ),
    ] = True,
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


@dataclass
class WriteCommandOptions:
    """Options for the write command."""

    input_file: Path
    source: SourceType
    output: Path
    step_size: int
    step_unit: WindowUnit
    overlap: float
    enable_enrichment: bool
    from_date: str | None
    to_date: str | None
    timezone: str | None
    model: str | None
    max_prompt_tokens: int
    use_full_context_window: bool
    max_windows: int | None
    resume: bool
    refresh: str | None
    force: bool
    debug: bool


def _validate_api_key(output_dir: Path) -> None:
    """Validate that API key is set and valid."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        _load_dotenv_if_available(output_dir)
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not api_key:
        console.print(
            "[red]Error: GOOGLE_API_KEY (or GEMINI_API_KEY) environment variable not set[/red]"
        )
        console.print(
            "Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable with your Google Gemini API key"
        )
        console.print(
            "You can also create a .env file in the output directory or current directory."
        )
        raise typer.Exit(1)

    # Validate the API key with a lightweight call
    console.print("[cyan]Validating Gemini API key...[/cyan]")
    try:
        validate_gemini_api_key(api_key)
        console.print("[green]✓ API key validated successfully[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
    except ImportError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


def _prepare_write_config(
    options: WriteCommandOptions, from_date_obj: date | None, to_date_obj: date | None
) -> Any:
    """Prepare Egregora configuration from options."""
    base_config = load_egregora_config(options.output)
    models_update: dict[str, str] = {}
    if options.model:
        models_update = {
            "writer": options.model,
            "enricher": options.model,
            "enricher_vision": options.model,
            "ranking": options.model,
            "editor": options.model,
        }
    return base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "step_size": options.step_size,
                    "step_unit": options.step_unit,
                    "overlap_ratio": options.overlap,
                    "timezone": options.timezone,
                    "from_date": from_date_obj.isoformat() if from_date_obj else None,
                    "to_date": to_date_obj.isoformat() if to_date_obj else None,
                    "max_prompt_tokens": options.max_prompt_tokens,
                    "use_full_context_window": options.use_full_context_window,
                    "max_windows": options.max_windows,
                    "checkpoint_enabled": options.resume,
                }
            ),
            "enrichment": base_config.enrichment.model_copy(
                update={"enabled": options.enable_enrichment}
            ),
            "rag": base_config.rag,
            **(
                {"models": base_config.models.model_copy(update=models_update)}
                if models_update
                else {}
            ),
        },
    )


def _resolve_write_options(
    input_file: Path,
    options_json: str | None,
    cli_defaults: dict[str, Any],
) -> WriteCommandOptions:
    """Merge CLI options with JSON options and defaults."""
    # Start with CLI values as base
    defaults = cli_defaults.copy()

    if options_json:
        try:
            overrides = json.loads(options_json)
            # Update with JSON overrides, converting enums if strings
            for k, v in overrides.items():
                if k == "source" and isinstance(v, str):
                    defaults[k] = SourceType(v)
                elif k == "step_unit" and isinstance(v, str):
                    defaults[k] = WindowUnit(v)
                elif k == "output" and isinstance(v, str):
                    defaults[k] = Path(v)
                else:
                    defaults[k] = v
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing options JSON: {e}[/red]")
            raise typer.Exit(1) from e

    return WriteCommandOptions(input_file=input_file, **defaults)


@app.command()
def write(  # noqa: PLR0913
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
    max_windows: Annotated[
        int | None, typer.Option(help="Limit number of windows to process")
    ] = None,
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
    cli_values = {
        "source": source,
        "output": output,
        "step_size": step_size,
        "step_unit": step_unit,
        "overlap": overlap,
        "enable_enrichment": enable_enrichment,
        "from_date": from_date,
        "to_date": to_date,
        "timezone": timezone,
        "model": model,
        "max_prompt_tokens": max_prompt_tokens,
        "use_full_context_window": use_full_context_window,
        "max_windows": max_windows,
        "resume": resume,
        "refresh": refresh,
        "force": force,
        "debug": debug,
    }

    parsed_options = _resolve_write_options(
        input_file=input_file,
        options_json=options,
        cli_defaults=cli_values,
    )

    if parsed_options.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    from_date_obj, to_date_obj = None, None
    if parsed_options.from_date:
        try:
            from_date_obj = parse_date_arg(parsed_options.from_date, "from_date")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e
    if parsed_options.to_date:
        try:
            to_date_obj = parse_date_arg(parsed_options.to_date, "to_date")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e

    if parsed_options.timezone:
        try:
            validate_timezone(parsed_options.timezone)
            console.print(f"[green]Using timezone: {parsed_options.timezone}[/green]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e

    output_dir = parsed_options.output.expanduser().resolve()
    _ensure_mkdocs_scaffold(output_dir)
    _validate_api_key(output_dir)

    egregora_config = _prepare_write_config(parsed_options, from_date_obj, to_date_obj)

    runtime = RuntimeContext(
        output_dir=output_dir,
        input_file=parsed_options.input_file,
        model_override=parsed_options.model,
        debug=parsed_options.debug,
    )

    try:
        console.print(
            Panel(
                f"[cyan]Source:[/cyan] {parsed_options.source.value}\n[cyan]Input:[/cyan] {parsed_options.input_file}\n[cyan]Output:[/cyan] {output_dir}\n[cyan]Windowing:[/cyan] {parsed_options.step_size} {parsed_options.step_unit.value}",
                title="⚙️  Egregora Pipeline",
                border_style="cyan",
            )
        )
        run_params = PipelineRunParams(
            output_dir=runtime.output_dir,
            config=egregora_config,
            source_type=parsed_options.source.value,
            input_path=runtime.input_file,
            refresh="all" if parsed_options.force else parsed_options.refresh,
        )
        write_pipeline.run(run_params)
        console.print("[green]Processing completed successfully.[/green]")
    except Exception as e:
        console.print_exception(show_locals=False)
        console.print(f"[red]Pipeline failed: {e}[/]")
        raise typer.Exit(code=1) from e


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
    # Deferred import to avoid circular dependencies or heavy load if not needed?
    # But for CLI entry points it is usually fine.
    # Moving import to top level as requested.
    # Note: Moving imports to top-level can cause circular imports if not careful.
    # But ruff insists. I will rely on Python handling modules.
    # If run_diagnostics imports config which imports main...
    # Main is entry point, config likely doesn't import main.
    # Diagnostics likely imports low level stuff.
    # I'll use a local import inside a helper function if needed, but ruff complains.
    # I'll try to move it to top level.
    _run_doctor_checks(verbose=verbose)


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
    console.print(
        f"[dim]Summary: {ok_count} OK, {warning_count} warnings, {error_count} errors[/dim]"
    )

    if error_count > 0:
        raise typer.Exit(1)
