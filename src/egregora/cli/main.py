"""Main Typer application for Egregora."""

import logging
import os
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from egregora.cli.runs import runs_app
from egregora.config import ProcessConfig, load_egregora_config
from egregora.config.config_validation import parse_date_arg, validate_retrieval_config
from egregora.init import ensure_mkdocs_project
from egregora.orchestration import write_pipeline

app = typer.Typer(
    name="egregora",
    help="Ultra-simple WhatsApp to blog pipeline with LLM-powered content generation",
    add_completion=False,
)
app.add_typer(runs_app)

# Simple logging setup (no telemetry)
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)
from egregora.constants import WindowUnit

logger = logging.getLogger(__name__)


@app.callback()
def main() -> None:
    """Initialize CLI (placeholder for future setup)."""


def _resolve_gemini_key(cli_override: str | None) -> str | None:
    """Return the Gemini API key honoring CLI override precedence."""
    if cli_override:
        os.environ["GOOGLE_API_KEY"] = cli_override
        return cli_override
    return os.getenv("GOOGLE_API_KEY")


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
) -> None:
    """Initialize a new MkDocs site scaffold for serving Egregora posts."""
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


def _setup_logging_and_validate_config(config: ProcessConfig):
    """Sets up logging and performs initial config validation."""
    if config.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    if config.timezone:
        try:
            ZoneInfo(config.timezone)
            console.print(f"[green]Using timezone: {config.timezone}[/green]")
        except Exception as e:
            console.print(f"[red]Invalid timezone '{config.timezone}': {e}[/red]")
            raise typer.Exit(1) from e
    try:
        validate_retrieval_config(config)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e


def _prepare_environment_and_config(config: ProcessConfig):
    """Prepares the environment, resolves paths, and builds the final config."""
    output_dir = config.output_dir.expanduser().resolve()
    config.output_dir = output_dir
    _ensure_mkdocs_scaffold(output_dir)
    api_key = _resolve_gemini_key(config.gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)

    base_config = load_egregora_config(output_dir)
    return base_config.model_copy(
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
    ), api_key


def _run_pipeline(source: str, config: ProcessConfig, egregora_config, api_key: str):
    """Runs the main write pipeline with error handling."""
    try:
        console.print(
            Panel(
                f"[cyan]Source:[/cyan] {source}\n[cyan]Input:[/cyan] {config.input_file}\n[cyan]Output:[/cyan] {config.output_dir}\n[cyan]Windowing:[/cyan] {config.step_size} {config.step_unit}",
                title="⚙️  Egregora Pipeline",
                border_style="cyan",
            )
        )
        write_pipeline.run(
            source=source,
            input_path=config.input_file,
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


def _validate_and_run_process(config: ProcessConfig, source: str = "whatsapp") -> None:
    """Orchestrates the validation and execution of the pipeline."""
    _setup_logging_and_validate_config(config)
    egregora_config, api_key = _prepare_environment_and_config(config)
    _run_pipeline(source, config, egregora_config, api_key)


@app.command()
def write(
    input_file: Annotated[Path, typer.Argument(help="Path to chat export file (ZIP, JSON, etc.)")],
    *,
    source: Annotated[str, typer.Option(help="Source type: 'whatsapp' or 'slack'")] = "whatsapp",
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
    # Parse date arguments
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
