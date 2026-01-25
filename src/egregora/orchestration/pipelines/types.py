"""Type definitions for orchestration pipelines.

This module contains dataclasses and type aliases used across the pipeline
orchestration layer, decoupling them from the main execution logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai

from egregora.config.defaults import PipelineDefaults
from egregora.constants import WindowUnit


@dataclass
class WriteCommandOptions:
    """Options for the write command."""

    input_file: Path
    source: str
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


@dataclass(frozen=True)
class WhatsAppProcessOptions:
    """Runtime overrides for :func:`process_whatsapp_export`."""

    output_dir: Path = Path("output")
    step_size: int = PipelineDefaults.STEP_SIZE
    step_unit: str | WindowUnit = PipelineDefaults.STEP_UNIT
    overlap_ratio: float = PipelineDefaults.OVERLAP_RATIO
    enable_enrichment: bool = True
    from_date: date_type | None = None
    to_date: date_type | None = None
    timezone: str | ZoneInfo | None = None
    gemini_api_key: str | None = None
    model: str | None = None
    batch_threshold: int = 10
    max_prompt_tokens: int = PipelineDefaults.MAX_PROMPT_TOKENS
    use_full_context_window: bool = PipelineDefaults.DEFAULT_USE_FULL_CONTEXT
    client: genai.Client | None = None
    refresh: str | None = None
