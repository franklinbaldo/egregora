"""Configuration resolution logic for the ETL pipeline.

Handles merging CLI arguments, JSON options, and configuration files.
"""

from __future__ import annotations

import json
from datetime import date as date_type
from pathlib import Path
from typing import Any

from rich.console import Console

from egregora.config import load_egregora_config
from egregora.config.settings import EgregoraConfig
from egregora.constants import WindowUnit
from egregora.orchestration.pipelines.types import WriteCommandOptions

console = Console()


def prepare_write_config(
    options: WriteCommandOptions, from_date_obj: date_type | None, to_date_obj: date_type | None
) -> Any:
    """Prepare Egregora configuration from options.

    Returns:
        EgregoraConfig object (typed as Any to avoid strict mypy check on model_copy deep update if complex)

    """
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


def resolve_write_options(
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


def resolve_sources_to_run(source: str | None, config: EgregoraConfig) -> list[tuple[str, str]]:
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
