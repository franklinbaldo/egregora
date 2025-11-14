"""Write command implementation."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from rich.panel import Panel

from egregora.cli import app, console, logger
from egregora.config import ProcessConfig, load_egregora_config
from egregora.config.config_validation import parse_date_arg, validate_retrieval_config
from egregora.init import ensure_mkdocs_project
from egregora.orchestration import write_pipeline


def _resolve_gemini_key(cli_override: str | None) -> str | None:
    """Return the Gemini API key honoring CLI override precedence."""
    if cli_override:
        os.environ["GOOGLE_API_KEY"] = cli_override
        return cli_override
    return os.getenv("GOOGLE_API_KEY")


def _ensure_mkdocs_scaffold(output_dir: Path) -> None:
    """Ensure site is initialized (has .egregora/config.yml), creating if needed."""
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


def _validate_and_run_process(config: ProcessConfig, source: str = "whatsapp") -> None:
    """Validate process configuration and run the pipeline."""
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

    output_dir = config.output_dir.expanduser().resolve()
    config.output_dir = output_dir

    _ensure_mkdocs_scaffold(output_dir)
    api_key = _resolve_gemini_key(config.gemini_key)
    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set[/red]")
        console.print("Provide via --gemini-key or set GOOGLE_API_KEY environment variable")
        raise typer.Exit(1)

    base_config = load_egregora_config(output_dir)

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
                    "nprobe": (
                        config.retrieval_nprobe
                        if config.retrieval_nprobe is not None
                        else base_config.rag.nprobe
                    ),
                    "overfetch": (
                        config.retrieval_overfetch
                        if config.retrieval_overfetch is not None
                        else base_config.rag.overfetch
                    ),
                }
            ),
        },
    )

    try:
        console.print(
            Panel(
                f"[cyan]Source:[/cyan] {source}\n"
                f"[cyan]Input:[/cyan] {config.input_file}\n"
                f"[cyan]Output:[/cyan] {output_dir}\n"
                f"[cyan]Windowing:[/cyan] {config.step_size} {config.step_unit}",
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
    """Write blog posts from chat exports using LLM-powered synthesis."""
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
