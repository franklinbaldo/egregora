"""Write pipeline orchestration - executes the complete write workflow.

This module orchestrates the high-level flow for the 'write' command, coordinating:
- Input adapter selection and parsing
- Privacy and enrichment stages
- Content generation with WriterWorker
- Command processing and announcement generation
- Profile generation (Egregora writing ABOUT authors)
- Background task processing
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from egregora.config import RuntimeContext, load_egregora_config
from egregora.config.defaults import PipelineDefaults
from egregora.constants import WindowUnit
from egregora.input_adapters import get_adapter_class
from egregora.llm.exceptions import AllModelsExhaustedError
from egregora.orchestration.context import PipelineRunParams
from egregora.orchestration.pipelines.coordination.background_tasks import (
    generate_taxonomy_task,
    process_background_tasks,
)
from egregora.orchestration.pipelines.etl.config_resolution import (
    prepare_write_config,
    resolve_sources_to_run,
    resolve_write_options,
)
from egregora.orchestration.pipelines.etl.preparation import (
    get_pending_conversations,
    prepare_pipeline_data,
    validate_dates,
    validate_timezone_arg,
)
from egregora.orchestration.pipelines.etl.setup import (
    ensure_site_initialized,
    pipeline_environment,
    validate_api_key,
)
from egregora.orchestration.pipelines.execution.processor import process_item
from egregora.orchestration.pipelines.types import WhatsAppProcessOptions, WriteCommandOptions

logger = logging.getLogger(__name__)
console = Console()
__all__ = ["WhatsAppProcessOptions", "WriteCommandOptions", "process_whatsapp_export", "run", "run_cli_flow"]


def run_cli_flow(
    input_file: Path,
    *,
    output: Path = Path("site"),
    source: str | None = None,
    step_size: int = PipelineDefaults.STEP_SIZE,
    step_unit: WindowUnit = PipelineDefaults.STEP_UNIT,
    overlap: float = PipelineDefaults.OVERLAP_RATIO,
    enable_enrichment: bool = True,
    from_date: str | None = PipelineDefaults.DEFAULT_FROM_DATE,
    to_date: str | None = PipelineDefaults.DEFAULT_TO_DATE,
    timezone: str | None = PipelineDefaults.DEFAULT_TIMEZONE,
    model: str | None = None,
    max_prompt_tokens: int = PipelineDefaults.MAX_PROMPT_TOKENS,
    use_full_context_window: bool = PipelineDefaults.DEFAULT_USE_FULL_CONTEXT,
    max_windows: int | None = PipelineDefaults.DEFAULT_MAX_WINDOWS,
    resume: bool = PipelineDefaults.DEFAULT_RESUME,
    refresh: str | None = None,
    force: bool = False,
    debug: bool = False,
    options: str | None = None,
    smoke_test: bool = False,
    exit_on_error: bool = True,
) -> None:
    """Execute the write flow from CLI arguments.

    Args:
        source: Can be a source type (e.g., "whatsapp"), a source key from config, or None.
                If None, will use default_source from config, or run all sources if default is None.
        exit_on_error: If True, raise SystemExit(1) on failure. If False, re-raise the exception.

    """
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

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    from_date_obj, to_date_obj = validate_dates(from_date, to_date)
    validate_timezone_arg(timezone)

    output_dir = output.expanduser().resolve()
<<<<<<< HEAD
    ensure_site_initialized(output_dir)
    try:
        validate_api_key(output_dir)
=======
    _ensure_site_initialized(output_dir)
    try:
        _validate_api_key(output_dir)
>>>>>>> origin/pr/2735
    except SystemExit as e:
        if exit_on_error:
            raise
        # Wrap SystemExit in RuntimeError so callers (like demo) can handle it gracefully
<<<<<<< HEAD
        msg = f"API key validation failed: {e}"
        raise RuntimeError(msg) from e
=======
        raise RuntimeError(f"API key validation failed: {e}") from e
>>>>>>> origin/pr/2735

    # Load config to determine sources
    base_config = load_egregora_config(output_dir)

    # Determine which sources to run
    sources_to_run = resolve_sources_to_run(source, base_config)

    # Process each source
    for source_key, source_type in sources_to_run:
        # Prepare options with current source
        parsed_options = resolve_write_options(
            input_file=input_file,
            options_json=options,
            cli_defaults={**cli_values, "source": source_type},
        )

        egregora_config = prepare_write_config(parsed_options, from_date_obj, to_date_obj)

        runtime = RuntimeContext(
            output_dir=output_dir,
            input_file=parsed_options.input_file,
            model_override=parsed_options.model,
            debug=parsed_options.debug,
        )

        try:
            console.print(
                Panel(
                    f"[cyan]Source:[/cyan] {source_type} (key: {source_key})\n[cyan]Input:[/cyan] {parsed_options.input_file}\n[cyan]Output:[/cyan] {output_dir}\n[cyan]Windowing:[/cyan] {parsed_options.step_size} {parsed_options.step_unit.value}",
                    title="⚙️  Egregora Pipeline",
                    border_style="cyan",
                )
            )
            run_params = PipelineRunParams(
                output_dir=runtime.output_dir,
                config=egregora_config,
                source_type=source_type,
                source_key=source_key,
                input_path=runtime.input_file,
                refresh="all" if parsed_options.force else parsed_options.refresh,
                smoke_test=smoke_test,
            )
            run(run_params)
            console.print(f"[green]Processing completed successfully for source '{source_key}'.[/green]")
        except (AllModelsExhaustedError, RuntimeError) as e:
            # Re-raise this specific error so the 'demo' command can catch it
            raise e
        except Exception as e:
            console.print_exception(show_locals=False)
            console.print(f"[red]Pipeline failed for source '{source_key}': {e}[/]")
            if exit_on_error:
                raise SystemExit(1) from e
            raise e


def process_whatsapp_export(
    zip_path: Path,
    *,
    options: WhatsAppProcessOptions | None = None,
) -> dict[str, dict[str, list[str]]]:
    """High-level helper for processing WhatsApp ZIP exports using :func:`run`."""
    opts = options or WhatsAppProcessOptions()
    output_dir = opts.output_dir.expanduser().resolve()

    if opts.gemini_api_key:
        os.environ["GOOGLE_API_KEY"] = opts.gemini_api_key

    base_config = load_egregora_config(output_dir)

    # Apply CLI model override to all text generation models if provided
    models_update = {}
    if opts.model:
        models_update = {
            "writer": opts.model,
            "enricher": opts.model,
            "enricher_vision": opts.model,
            "ranking": opts.model,
            "editor": opts.model,
        }

    egregora_config = base_config.model_copy(
        deep=True,
        update={
            "pipeline": base_config.pipeline.model_copy(
                update={
                    "step_size": opts.step_size,
                    "step_unit": opts.step_unit,
                    "overlap_ratio": opts.overlap_ratio,
                    "timezone": str(opts.timezone) if opts.timezone else None,
                    "from_date": opts.from_date.isoformat() if opts.from_date else None,
                    "to_date": opts.to_date.isoformat() if opts.to_date else None,
                    "batch_threshold": opts.batch_threshold,
                    "max_prompt_tokens": opts.max_prompt_tokens,
                    "use_full_context_window": opts.use_full_context_window,
                }
            ),
            "enrichment": base_config.enrichment.model_copy(update={"enabled": opts.enable_enrichment}),
            # RAG settings: no runtime overrides needed (uses config from .egregora/config.yml)
            "rag": base_config.rag,
            **({"models": base_config.models.model_copy(update=models_update)} if models_update else {}),
        },
    )

    run_params = PipelineRunParams(
        output_dir=output_dir,
        config=egregora_config,
        source_type="whatsapp",
        input_path=zip_path,
        client=opts.client,
        refresh=opts.refresh,
    )

    return run(run_params)


def run(run_params: PipelineRunParams) -> dict[str, dict[str, list[str]]]:
    """Run the complete write pipeline workflow.

    Args:
        run_params: Aggregated pipeline run parameters

    Returns:
        Dict mapping window labels to {'posts': [...], 'profiles': [...]}

    """
    logger.info("[bold cyan]🚀 Starting pipeline for source:[/] %s", run_params.source_type)

    # Create adapter with config for privacy settings
    # Instead of using singleton from registry, instantiate with config
    adapter_cls = get_adapter_class(run_params.source_type)

    # Instantiate adapter with config if it supports it (WhatsApp does)
    try:
        adapter = adapter_cls(config=run_params.config)
    except TypeError:
        # Fallback for adapters that don't accept config parameter
        adapter = adapter_cls()

    with pipeline_environment(run_params) as ctx:
        try:
            dataset = prepare_pipeline_data(adapter, run_params, ctx)

            results = {}
            max_processed_timestamp: datetime | None = None

            # New simplified loop: Iterator (ETL) -> Process (Execution)
            for conversation in get_pending_conversations(dataset):
                item_results = process_item(conversation)
                results.update(item_results)

                # Track max timestamp for checkpoint
                if max_processed_timestamp is None or conversation.window.end_time > max_processed_timestamp:
                    max_processed_timestamp = conversation.window.end_time

            generate_taxonomy_task(dataset)

            # Final pass for any lingering background tasks
            process_background_tasks(dataset.context)

            # Regenerate tags page with word cloud visualization
            if hasattr(dataset.context.output_sink, "regenerate_tags_page"):
                try:
                    logger.info("[bold cyan]🏷️  Regenerating tags page with word cloud...[/]")
                    dataset.context.output_sink.regenerate_tags_page()
                except (OSError, AttributeError, TypeError) as e:
                    logger.warning("Failed to regenerate tags page: %s", e)

            logger.info("[bold green]🎉 Pipeline completed successfully![/]")

        except KeyboardInterrupt:
            logger.warning("[yellow]⚠️  Pipeline cancelled by user (Ctrl+C)[/]")
            raise  # Re-raise to allow proper cleanup
        except Exception:
            # Broad catch is intentional: record failure for any exception, then re-raise
            raise  # Re-raise original exception to preserve error context

        return results
