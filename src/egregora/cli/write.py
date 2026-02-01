"""CLI logic for the write command.

This module handles configuration resolution, validation, and entry points
for the 'write' command, bridging CLI arguments to the pipeline orchestration.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from egregora.config import RuntimeContext, load_egregora_config
from egregora.config.settings import EgregoraConfig
from egregora.constants import WindowUnit
from egregora.orchestration.context import PipelineRunParams
from egregora.orchestration.pipelines.etl.preparation import (
    validate_dates,
    validate_timezone_arg,
)
from egregora.orchestration.pipelines.etl.setup import (
    ensure_site_initialized,
    validate_api_key,
)
from egregora.orchestration.pipelines.types import (
    WhatsAppProcessOptions,
    WriteCommandOptions,
)
from egregora.orchestration.pipelines.write import run

logger = logging.getLogger(__name__)
console = Console()

__all__ = ["process_whatsapp_export", "run_cli_flow"]


def _prepare_write_config(
    options: WriteCommandOptions,
    from_date_obj: Any,  # Using Any to match imported return type or date_type
    to_date_obj: Any,
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
                if k == "step_unit" and isinstance(v, str):
                    defaults[k] = WindowUnit(v)
                elif k == "output" and isinstance(v, str):
                    defaults[k] = Path(v)
                else:
                    defaults[k] = v
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing options JSON: {e}[/red]")
            raise SystemExit(1) from e

    return WriteCommandOptions(input_file=input_file, **defaults)


def _resolve_sources_to_run(source: str | None, config: EgregoraConfig) -> list[tuple[str, str]]:
    """Resolve which sources to run based on CLI argument and config.

    Args:
        source: Source key, source type, or None
        config: Egregora configuration

    Returns:
        List of (source_key, source_type) tuples to process

    Raises:
        SystemExit: If source is unknown

    """
    # If source is explicitly provided
    if source is not None:
        # Check if it's a source key
        if source in config.site.sources:
            source_config = config.site.sources[source]
            return [(source, source_config.adapter)]

        # Check if it's a source type (adapter name) - find first matching source
        for key, src_config in config.site.sources.items():
            if src_config.adapter == source:
                return [(key, source)]

        # Unknown source
        available_keys = ", ".join(config.site.sources.keys())
        available_types = ", ".join({s.adapter for s in config.site.sources.values()})
        console.print(
            f"[red]Error: Unknown source '{source}'.[/red]\n"
            f"Available source keys: {available_keys}\n"
            f"Available source types: {available_types}"
        )
        raise SystemExit(1)

    # source is None - use default or run all
    if config.site.default_source is None:
        # Run all configured sources
        return [(key, src.adapter) for key, src in config.site.sources.items()]

    # Use default source
    default_key = config.site.default_source
    if default_key not in config.site.sources:
        console.print(f"[red]Error: default_source '{default_key}' not found in configured sources.[/red]")
        raise SystemExit(1)

    return [(default_key, config.site.sources[default_key].adapter)]


def run_cli_flow(
    input_file: Path,
    *,
    output: Path = Path("site"),
    source: str | None = None,
    step_size: int = 100,
    step_unit: WindowUnit = WindowUnit.MESSAGES,
    overlap: float = 0.0,
    enable_enrichment: bool = True,
    from_date: str | None = None,
    to_date: str | None = None,
    timezone: str | None = None,
    model: str | None = None,
    max_prompt_tokens: int = 400000,
    use_full_context_window: bool = False,
    max_windows: int | None = None,
    resume: bool = True,
    refresh: str | None = None,
    force: bool = False,
    debug: bool = False,
    report_health: bool = False,
    options: str | None = None,
    smoke_test: bool = False,
) -> None:
    """Execute the write flow from CLI arguments.

    Args:
        source: Can be a source type (e.g., "whatsapp"), a source key from config, or None.
                If None, will use default_source from config, or run all sources if default is None.

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
    ensure_site_initialized(output_dir)
    validate_api_key(output_dir)

    # Load config to determine sources
    base_config = load_egregora_config(output_dir)

    # Determine which sources to run
    sources_to_run = _resolve_sources_to_run(source, base_config)

    # Process each source
    for source_key, source_type in sources_to_run:
        # Prepare options with current source
        parsed_options = _resolve_write_options(
            input_file=input_file,
            options_json=options,
            cli_defaults={**cli_values, "source": source_type},
        )

        egregora_config = _prepare_write_config(parsed_options, from_date_obj, to_date_obj)

        # Apply --report-health CLI flag override
        if report_health:
            egregora_config = egregora_config.model_copy(
                deep=True,
                update={
                    "features": egregora_config.features.model_copy(update={"report_health_enabled": True}),
                },
            )

        runtime = RuntimeContext(
            output_dir=output_dir,
            input_file=parsed_options.input_file,
            model_override=parsed_options.model,
            debug=parsed_options.debug,
        )

        console.print(
            Panel(
                f"[cyan]Source:[/cyan] {source_type} (key: {source_key})\n"
                f"[cyan]Input:[/cyan] {parsed_options.input_file}\n"
                f"[cyan]Output:[/cyan] {output_dir}\n"
                f"[cyan]Windowing:[/cyan] {parsed_options.step_size} {parsed_options.step_unit.value}",
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
