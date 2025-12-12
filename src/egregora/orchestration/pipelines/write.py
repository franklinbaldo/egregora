"""Orchestration for the write command.

This module encapsulates the high-level orchestration logic for the 'write' command,
including option resolution, configuration preparation, and environment validation,
before delegating to the core execution pipeline.
"""

import logging
import os
from datetime import date
from typing import Any

import typer
from rich.console import Console

from egregora.config import RuntimeContext, load_egregora_config
from egregora.config.config_validation import parse_date_arg, validate_timezone
from egregora.init import ensure_mkdocs_project
from egregora.orchestration import write_pipeline
from egregora.orchestration.context import PipelineRunParams

# Typer is used here only for exceptions and type hints related to CLI options,
# avoiding direct CLI dependency in orchestration logic where possible,
# but since this module bridges CLI and Pipeline, it is acceptable.

logger = logging.getLogger(__name__)
console = Console()


try:
    import dotenv
except ImportError:
    dotenv = None


def _load_dotenv_if_available(output_dir: Any) -> None:
    if dotenv:
        dotenv.load_dotenv(output_dir / ".env")
        dotenv.load_dotenv()  # Check CWD as well


def _validate_api_key(output_dir: Any) -> None:
    """Validate that API key is set."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        return

    _load_dotenv_if_available(output_dir)

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    if not api_key:
        console.print("[red]Error: GOOGLE_API_KEY (or GEMINI_API_KEY) environment variable not set[/red]")
        console.print(
            "Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable with your Google Gemini API key"
        )
        console.print("You can also create a .env file in the output directory or current directory.")
        raise typer.Exit(1)


def _ensure_mkdocs_scaffold(output_dir: Any) -> None:
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


def _prepare_write_config(
    options: Any, from_date_obj: date | None, to_date_obj: date | None
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
            "enrichment": base_config.enrichment.model_copy(update={"enabled": options.enable_enrichment}),
            "rag": base_config.rag,
            **({"models": base_config.models.model_copy(update=models_update)} if models_update else {}),
        },
    )


class WritePipeline:
    """Pipeline orchestrator for the write command."""

    def run(self, options: Any) -> None:
        """Run the write pipeline with the given options."""
        if options.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        from_date_obj, to_date_obj = None, None
        if options.from_date:
            try:
                from_date_obj = parse_date_arg(options.from_date, "from_date")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1) from e
        if options.to_date:
            try:
                to_date_obj = parse_date_arg(options.to_date, "to_date")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1) from e

        if options.timezone:
            try:
                validate_timezone(options.timezone)
                console.print(f"[green]Using timezone: {options.timezone}[/green]")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1) from e

        output_dir = options.output.expanduser().resolve()
        _ensure_mkdocs_scaffold(output_dir)
        _validate_api_key(output_dir)

        egregora_config = _prepare_write_config(options, from_date_obj, to_date_obj)

        runtime = RuntimeContext(
            output_dir=output_dir,
            input_file=options.input_file,
            model_override=options.model,
            debug=options.debug,
        )

        # We construct run_params and delegate to the core write pipeline
        run_params = PipelineRunParams(
            output_dir=runtime.output_dir,
            config=egregora_config,
            source_type=options.source.value,
            input_path=runtime.input_file,
            refresh="all" if options.force else options.refresh,
        )
        write_pipeline.run(run_params)
