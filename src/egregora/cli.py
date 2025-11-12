"""Typer-based CLI for Egregora v2."""

import logging
import os
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from egregora.config import ProcessConfig, load_egregora_config
from egregora.config.validation import parse_date_arg, validate_retrieval_config
from egregora.init import ensure_mkdocs_project
from egregora.orchestration import write_pipeline

app = typer.Typer(
    name="egregora",
    help="Ultra-simple WhatsApp to blog pipeline with LLM-powered content generation",
    add_completion=False,
)

# Simple logging setup (no telemetry)
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger(__name__)


@app.callback()
def _initialize_cli() -> None:
    """Initialize CLI (placeholder for future setup)."""


def _resolve_gemini_key(cli_override: str | None) -> str | None:
    """Return the Gemini API key honoring CLI override precedence.

    If a CLI override is provided, it will be set in the GOOGLE_API_KEY
    environment variable so that all subsequent code (including pydantic-ai
    agents) can access it without explicit passing.
    """
    if cli_override:
        os.environ["GOOGLE_API_KEY"] = cli_override
        return cli_override
    return os.getenv("GOOGLE_API_KEY")


def _ensure_mkdocs_scaffold(output_dir: Path) -> None:
    """Ensure site is initialized (has .egregora/config.yml), creating if needed with user confirmation.

    Phase 4: Extracted from _validate_and_run_process to reduce complexity.

    Args:
        output_dir: Output directory to check/initialize

    Raises:
        typer.Exit: If user declines to initialize or initialization fails

    """
    config_path = output_dir / ".egregora" / "config.yml"
    if config_path.exists():
        return  # Site already initialized

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
) -> None:
    """Initialize a new MkDocs site scaffold for serving Egregora posts.

    Creates:
    - mkdocs.yml with Material theme + blog plugin
    - Directory structure (docs/, posts/, profiles/, media/)
    - README.md with quick start instructions
    - .gitignore for Python and MkDocs
    - Starter pages (homepage, about, profiles index)
    """
    site_root = output_dir.resolve()
    docs_dir, mkdocs_created = ensure_mkdocs_project(site_root)
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


def _validate_and_run_process(config: ProcessConfig, source: str = "whatsapp") -> None:
    """Validate process configuration and run the pipeline.

    Phase 4: Simplified by extracting validation logic to helper functions.
    """
    if config.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate timezone
    if config.timezone:
        try:
            ZoneInfo(config.timezone)
            console.print(f"[green]Using timezone: {config.timezone}[/green]")
        except Exception as e:
            console.print(f"[red]Invalid timezone '{config.timezone}': {e}[/red]")
            raise typer.Exit(1) from e

    # Phase 4: Extracted validation logic
    try:
        validate_retrieval_config(config)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    # Resolve and ensure output directory
    output_dir = config.output_dir.expanduser().resolve()
    config.output_dir = output_dir

    # Phase 4: Extracted scaffold initialization logic
    _ensure_mkdocs_scaffold(output_dir)
    api_key = _resolve_gemini_key(config.gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)

    # Load or create EgregoraConfig (Phase 2: reduces parameters)
    base_config = load_egregora_config(output_dir)

    # Override config values from CLI flags using model_copy
    egregora_config = base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "step_size": config.step_size,
                    "step_unit": config.step_unit,
                    "overlap_ratio": config.overlap_ratio,
                    "timezone": config.timezone,
                    "from_date": config.from_date.isoformat() if config.from_date else None,
                    "to_date": config.to_date.isoformat() if config.to_date else None,
                    "max_prompt_tokens": config.max_prompt_tokens,
                    "use_full_context_window": config.use_full_context_window,
                }
            ),
            "enrichment": base_config.enrichment.model_copy(update={"enabled": config.enable_enrichment}),
            "rag": base_config.rag.model_copy(
                update={
                    "mode": config.retrieval_mode or base_config.rag.mode,
                    "nprobe": config.retrieval_nprobe
                    if config.retrieval_nprobe is not None
                    else base_config.rag.nprobe,
                    "overfetch": config.retrieval_overfetch
                    if config.retrieval_overfetch is not None
                    else base_config.rag.overfetch,
                }
            ),
        },
    )

    try:
        console.print(
            Panel(
                f"[cyan]Source:[/cyan] {source}\n[cyan]Input:[/cyan] {config.zip_file}\n[cyan]Output:[/cyan] {output_dir}\n[cyan]Windowing:[/cyan] {config.step_size} {config.step_unit}",
                title="⚙️  Egregora Pipeline",
                border_style="cyan",
            )
        )
        write_pipeline.run(
            source=source,
            input_path=config.zip_file,
            output_dir=config.output_dir,
            config=egregora_config,
            api_key=api_key,
            model_override=config.model,
        )
        console.print("[green]Processing completed successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Pipeline failed: {e}[/red]")
        if config.debug:
            raise
        raise typer.Exit(1) from e


@app.command()
def write(
    input_file: Annotated[Path, typer.Argument(help="Path to chat export file (ZIP, JSON, etc.)")],
    *,
    source: Annotated[str, typer.Option(help="Source type: 'whatsapp' or 'slack'")] = "whatsapp",
    output: Annotated[Path, typer.Option(help="Output directory for generated site")] = Path("output"),
    step_size: Annotated[int, typer.Option(help="Size of each processing window")] = 1,
    step_unit: Annotated[str, typer.Option(help="Unit for windowing: 'messages', 'hours', 'days'")] = "days",
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
    gemini_key: Annotated[
        str | None, typer.Option(help="Google Gemini API key (flag overrides GOOGLE_API_KEY env var)")
    ] = None,
    model: Annotated[
        str | None, typer.Option(help="Gemini model to use (or configure in mkdocs.yml)")
    ] = None,
    retrieval_mode: Annotated[
        str, typer.Option(help="Retrieval strategy: 'ann' (default) or 'exact'", case_sensitive=False)
    ] = "ann",
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
    # Parse date arguments using validation module
    from_date_obj = None
    to_date_obj = None
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
    config = ProcessConfig(
        input_file=input_file,
        output_dir=output,
        step_size=step_size,
        step_unit=step_unit,
        overlap_ratio=overlap,
        enable_enrichment=enable_enrichment,
        from_date=from_date_obj,
        to_date=to_date_obj,
        timezone=timezone,
        gemini_key=gemini_key,
        model=model,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
        max_prompt_tokens=max_prompt_tokens,
        use_full_context_window=use_full_context_window,
        debug=debug,
    )
    _validate_and_run_process(config, source=source)


@app.command(name="doctor")
def doctor(
    *,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed diagnostic information")
    ] = False,
) -> None:
    """Run diagnostic checks to verify Egregora setup.

    Checks:
    - Python version (3.12+)
    - Required packages
    - API key configuration
    - DuckDB VSS extension
    - Git availability
    - Cache directory permissions
    - Egregora config validity
    - Available source adapters

    Examples:
        egregora doctor          # Run all checks
        egregora doctor -v       # Show detailed output

    """
    from egregora.diagnostics import HealthStatus, run_diagnostics

    console.print("[bold cyan]Running diagnostics...[/bold cyan]")
    console.print()

    results = run_diagnostics()

    # Count status levels
    ok_count = sum(1 for r in results if r.status == HealthStatus.OK)
    warning_count = sum(1 for r in results if r.status == HealthStatus.WARNING)
    error_count = sum(1 for r in results if r.status == HealthStatus.ERROR)

    # Display results
    for result in results:
        # Status icon and color
        if result.status == HealthStatus.OK:
            icon = "✅"
            color = "green"
        elif result.status == HealthStatus.WARNING:
            icon = "⚠️"
            color = "yellow"
        elif result.status == HealthStatus.ERROR:
            icon = "❌"
            color = "red"
        else:  # INFO
            icon = "ℹ️"
            color = "cyan"

        # Print check result
        console.print(f"[{color}]{icon} {result.check}:[/{color}] {result.message}")

        # Show details if verbose
        if verbose and result.details:
            for key, value in result.details.items():
                console.print(f"    {key}: {value}", style="dim")

    # Summary
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

    # Exit with error code if any errors found
    if error_count > 0:
        raise typer.Exit(1)


# ==============================================================================
# View Registry Commands
# ==============================================================================

views_app = typer.Typer(
    name="views",
    help="Manage database views and materialized views",
)
app.add_typer(views_app)


@views_app.command(name="list")
def views_list(
    db_path: Annotated[
        Path | None, typer.Option(help="Database file path (uses in-memory DB if not specified)")
    ] = None,
) -> None:
    """List all registered views.

    Examples:
        egregora views list
        egregora views list --db-path=pipeline.db

    """
    import duckdb

    from egregora.database.views import ViewRegistry, register_common_views

    # Connect to database
    conn = duckdb.connect(str(db_path) if db_path else ":memory:")

    try:
        # Create registry and register common views
        registry = ViewRegistry(conn)
        register_common_views(registry)

        views = registry.list_views()

        if not views:
            console.print("[yellow]No views registered[/yellow]")
            return

        console.print(f"[cyan]Registered views ({len(views)}):[/cyan]")
        console.print()

        for view_name in sorted(views):
            view = registry.get_view(view_name)
            materialized = "📊 materialized" if view.materialized else "👁️  view"
            console.print(f"  • [bold]{view_name}[/bold] [{materialized}]")

            if view.description:
                console.print(f"    {view.description}", style="dim")

            if view.dependencies:
                deps = ", ".join(view.dependencies)
                console.print(f"    Dependencies: {deps}", style="dim")

            console.print()

    finally:
        conn.close()


@views_app.command(name="create")
def views_create(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
    force: Annotated[bool, typer.Option("--force", "-f", help="Drop existing views before creating")] = False,
) -> None:
    """Create all registered views in the database.

    Examples:
        egregora views create pipeline.db
        egregora views create pipeline.db --table-name=conversations
        egregora views create pipeline.db --force  # Recreate existing views

    """
    import duckdb

    from egregora.database.views import ViewRegistry, register_common_views

    if not db_path.exists():
        console.print(f"[red]Error: Database file not found: {db_path}[/red]")
        raise typer.Exit(1)

    # Connect to database
    conn = duckdb.connect(str(db_path))

    # Verify table exists
    tables = conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
    table_names = [t[0] for t in tables]

    if table_name not in table_names:
        conn.close()
        console.print(f"[red]Error: Table '{table_name}' not found in database[/red]")
        console.print(f"Available tables: {', '.join(table_names)}")
        raise typer.Exit(1)

    try:
        # Create registry and register common views
        registry = ViewRegistry(conn)
        register_common_views(registry, table_name=table_name)

        # Create views
        console.print(f"[cyan]Creating {len(registry.list_views())} views...[/cyan]")
        registry.create_all(force=force)

        console.print(f"[green]✅ Created {len(registry.list_views())} views[/green]")

    except Exception as e:
        console.print(f"[red]Error creating views: {e}[/red]")
        raise typer.Exit(1) from e

    finally:
        conn.close()


@views_app.command(name="refresh")
def views_refresh(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    view_name: Annotated[
        str | None, typer.Option(help="Specific view to refresh (refreshes all if not specified)")
    ] = None,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
) -> None:
    """Refresh materialized views with fresh data.

    Examples:
        egregora views refresh pipeline.db                 # Refresh all
        egregora views refresh pipeline.db --view-name=author_message_counts  # Refresh specific view

    """
    import duckdb

    from egregora.database.views import ViewRegistry, register_common_views

    if not db_path.exists():
        console.print(f"[red]Error: Database file not found: {db_path}[/red]")
        raise typer.Exit(1)

    # Connect to database
    conn = duckdb.connect(str(db_path))

    # Create registry and register common views
    registry = ViewRegistry(conn)
    register_common_views(registry, table_name=table_name)

    if view_name:
        # Validate specific view
        if view_name not in registry.list_views():
            conn.close()
            console.print(f"[red]Error: View '{view_name}' not registered[/red]")
            console.print(f"Available views: {', '.join(registry.list_views())}")
            raise typer.Exit(1)

        view = registry.get_view(view_name)
        if not view.materialized:
            conn.close()
            console.print(f"[yellow]Warning: '{view_name}' is not materialized (cannot refresh)[/yellow]")
            raise typer.Exit(1)

    try:
        if view_name:
            # Refresh specific view
            console.print(f"[cyan]Refreshing view: {view_name}...[/cyan]")
            registry.refresh(view_name)
            console.print(f"[green]✅ Refreshed {view_name}[/green]")

        else:
            # Refresh all materialized views
            materialized_views = [name for name, view in registry.views.items() if view.materialized]

            if not materialized_views:
                console.print("[yellow]No materialized views to refresh[/yellow]")
                return

            console.print(f"[cyan]Refreshing {len(materialized_views)} materialized views...[/cyan]")
            registry.refresh_all()
            console.print(f"[green]✅ Refreshed {len(materialized_views)} views[/green]")

    except Exception as e:
        console.print(f"[red]Error refreshing views: {e}[/red]")
        raise typer.Exit(1) from e

    finally:
        conn.close()


@views_app.command(name="drop")
def views_drop(
    db_path: Annotated[Path, typer.Argument(help="Database file path")],
    *,
    view_name: Annotated[
        str | None, typer.Option(help="Specific view to drop (drops all if not specified)")
    ] = None,
    table_name: Annotated[str, typer.Option(help="Name of the messages table")] = "messages",
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
) -> None:
    """Drop views from the database.

    Examples:
        egregora views drop pipeline.db                 # Drop all
        egregora views drop pipeline.db --view-name=author_message_counts  # Drop specific view
        egregora views drop pipeline.db --force         # Skip confirmation

    """
    import duckdb

    from egregora.database.views import ViewRegistry, register_common_views

    if not db_path.exists():
        console.print(f"[red]Error: Database file not found: {db_path}[/red]")
        raise typer.Exit(1)

    # Connect to database
    conn = duckdb.connect(str(db_path))

    # Create registry and register common views
    registry = ViewRegistry(conn)
    register_common_views(registry, table_name=table_name)

    if view_name:
        # Validate specific view
        if view_name not in registry.list_views():
            conn.close()
            console.print(f"[red]Error: View '{view_name}' not registered[/red]")
            console.print(f"Available views: {', '.join(registry.list_views())}")
            raise typer.Exit(1)

        # Confirm before dropping (unless --force)
        if not force:
            console.print(f"[yellow]About to drop view: {view_name}[/yellow]")
            confirm = typer.confirm("Continue?")
            if not confirm:
                conn.close()
                console.print("[cyan]Cancelled[/cyan]")
                raise typer.Exit(0)
    else:
        # Check if there are views to drop
        view_count = len(registry.list_views())

        if view_count == 0:
            conn.close()
            console.print("[yellow]No views to drop[/yellow]")
            return

        # Confirm before dropping (unless --force)
        if not force:
            console.print(f"[yellow]About to drop {view_count} views[/yellow]")
            confirm = typer.confirm("Continue?")
            if not confirm:
                conn.close()
                console.print("[cyan]Cancelled[/cyan]")
                raise typer.Exit(0)

    try:
        if view_name:
            # Drop specific view
            registry.drop(view_name)
            console.print(f"[green]✅ Dropped {view_name}[/green]")
        else:
            # Drop all views
            view_count = len(registry.list_views())
            registry.drop_all()
            console.print(f"[green]✅ Dropped {view_count} views[/green]")

    except Exception as e:
        console.print(f"[red]Error dropping views: {e}[/red]")
        raise typer.Exit(1) from e

    finally:
        conn.close()


# ==============================================================================
# Run Tracking Commands
# ==============================================================================

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
    """Show last N runs.

    Examples:
        egregora runs tail              # Last 10 runs
        egregora runs tail --n 20       # Last 20 runs

    """
    import duckdb
    from rich.table import Table

    if not db_path.exists():
        console.print(f"[yellow]No runs database found at {db_path}[/yellow]")
        console.print("[dim]Runs will be tracked after first pipeline execution[/dim]")
        return

    # Connect to runs database
    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        # Query last N runs
        result = conn.execute(
            """
            SELECT
                run_id,
                stage,
                status,
                started_at,
                rows_in,
                rows_out,
                duration_seconds
            FROM runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            [n],
        ).fetchall()

        if not result:
            console.print("[yellow]No runs found[/yellow]")
            return

        # Create Rich table
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

            # Color-code status
            if status == "completed":
                status_text = f"[green]{status}[/green]"
            elif status == "failed":
                status_text = f"[red]{status}[/red]"
            elif status == "running":
                status_text = f"[yellow]{status}[/yellow]"
            else:
                status_text = status

            # Format duration
            duration_text = f"{duration:.2f}s" if duration is not None else "-"

            # Format rows
            rows_in_text = str(rows_in) if rows_in is not None else "-"
            rows_out_text = str(rows_out) if rows_out is not None else "-"

            # Truncate run_id for display
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
    db_path: Annotated[Path, typer.Option(help="Runs database path")] = Path(".egregora-cache/runs.duckdb"),
) -> None:
    """Show detailed run info.

    Examples:
        egregora runs show a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11
        egregora runs show a0eebc99  # Prefix matching

    """
    import duckdb
    from rich.panel import Panel

    if not db_path.exists():
        console.print(f"[red]No runs database found at {db_path}[/red]")
        raise typer.Exit(1)

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        result = conn.execute(
            """
            SELECT
                run_id, tenant_id, stage, status, error,
                input_fingerprint, code_ref, config_hash,
                started_at, finished_at, duration_seconds,
                rows_in, rows_out, llm_calls, tokens, trace_id
            FROM runs
            WHERE CAST(run_id AS VARCHAR) LIKE ?
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
