"""Core Pipeline Orchestrator - source-agnostic pipeline execution engine.

This module implements the main orchestration logic that runs pipeline stages
in sequence, managing checkpoints, context, and error handling. The orchestrator
is completely source-agnostic and works with any SourceAdapter implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ibis.expr.types import Table

from egregora.pipeline.adapters import SourceAdapter
from egregora.pipeline.base import PipelineStage, StageResult
from egregora.pipeline.ir import validate_ir_schema

__all__ = [
    "PipelineContext",
    "PipelineConfig",
    "CoreOrchestrator",
]

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Shared context passed between pipeline stages.

    This allows stages to share data and artifacts without tight coupling.
    """

    # Source information
    source_name: str
    input_path: Path
    output_dir: Path

    # Artifacts from stages (media mappings, file paths, etc.)
    artifacts: dict[str, Any] = field(default_factory=dict)

    # Processing metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Metrics accumulated across stages
    metrics: dict[str, int | float] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""

    # Input/output
    input_path: Path
    output_dir: Path

    # Processing options
    period: str = "day"  # "day", "week", or "month"
    timezone: str | None = None

    # Stage options
    enable_enrichment: bool = True
    enable_rag: bool = True

    # Resume capability
    resume: bool = True
    checkpoint_dir: Path = Path(".egregora/checkpoints")

    # Performance tuning
    batch_threshold: int = 10

    # Date filtering
    from_date: Any = None  # date object or None
    to_date: Any = None  # date object or None

    # Model configuration (passed to stages that need it)
    model_config: Any = None  # ModelConfig instance

    # API keys and clients
    gemini_api_key: str | None = None
    client: Any = None  # genai.Client instance

    # RAG configuration
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None

    # Additional stage-specific params
    stage_params: dict[str, dict[str, Any]] = field(default_factory=dict)


class CoreOrchestrator:
    """Source-agnostic pipeline orchestrator.

    The orchestrator manages:
    1. Parsing input via SourceAdapter
    2. Running pipeline stages in sequence
    3. Managing shared context between stages
    4. Handling checkpoints and resume logic
    5. Error handling and logging

    Example:
        >>> from egregora.pipeline import CoreOrchestrator, PipelineConfig
        >>> from egregora.adapters.whatsapp import WhatsAppAdapter
        >>> from egregora.pipeline.stages import create_standard_stages
        >>>
        >>> config = PipelineConfig(
        ...     input_path=Path("export.zip"),
        ...     output_dir=Path("output"),
        ... )
        >>> adapter = WhatsAppAdapter()
        >>> stages = create_standard_stages(config)
        >>> orchestrator = CoreOrchestrator(adapter, stages)
        >>> result = orchestrator.run(config)
    """

    def __init__(
        self,
        source_adapter: SourceAdapter,
        stages: list[PipelineStage],
    ):
        """Initialize the orchestrator.

        Args:
            source_adapter: Adapter for parsing the source format
            stages: List of pipeline stages to execute in order
        """
        self.source_adapter = source_adapter
        self.stages = stages

    def run(self, config: PipelineConfig) -> dict[str, Any]:
        """Execute the complete pipeline.

        Args:
            config: Pipeline configuration

        Returns:
            Dictionary with pipeline results and metrics

        Raises:
            ValueError: If input is invalid or IR schema validation fails
            RuntimeError: If pipeline execution fails
        """
        logger.info(f"[bold cyan]🚀 Starting pipeline:[/] {self.source_adapter.source_name}")
        logger.info(f"[cyan]Input:[/] {config.input_path}")
        logger.info(f"[cyan]Output:[/] {config.output_dir}")

        # Initialize context
        context = PipelineContext(
            source_name=self.source_adapter.source_identifier,
            input_path=config.input_path,
            output_dir=config.output_dir,
        )

        # Step 1: Parse input with source adapter
        logger.info(f"[bold cyan]📦 Parsing with adapter:[/] {self.source_adapter.source_name}")
        messages_table = self.source_adapter.parse(
            config.input_path,
            timezone=config.timezone,
        )

        # Validate IR schema compliance
        is_valid, errors = validate_ir_schema(messages_table)
        if not is_valid:
            raise ValueError(
                f"Source adapter produced invalid IR schema. Errors:\n" +
                "\n".join(f"  - {err}" for err in errors)
            )

        total_messages = messages_table.count().execute()
        logger.info(f"[green]✅ Parsed[/] {total_messages} messages")
        context.metrics["total_messages"] = total_messages

        # Step 2: Extract media (if supported by adapter)
        try:
            media_mapping = self.source_adapter.extract_media(
                config.input_path,
                config.output_dir,
            )
            if media_mapping:
                logger.info(f"[green]📎 Extracted[/] {len(media_mapping)} media files")
                context.artifacts["media_mapping"] = media_mapping
        except NotImplementedError:
            logger.debug(f"Source adapter {self.source_adapter.source_name} does not support media extraction")

        # Step 3: Get metadata (if available)
        try:
            metadata = self.source_adapter.get_metadata(config.input_path)
            context.metadata.update(metadata)
            if metadata:
                logger.info(f"[cyan]ℹ️  Metadata:[/] {metadata}")
        except Exception as e:
            logger.debug(f"Could not extract metadata: {e}")

        # Step 4: Run pipeline stages
        current_data = messages_table
        for stage in self.stages:
            # Skip disabled stages
            if not stage.config.enabled:
                logger.info(f"[yellow]⏭️  Skipping disabled stage:[/] {stage.stage_name}")
                continue

            logger.info(f"[bold cyan]▶️  Running stage:[/] {stage.stage_name}")

            # Validate input
            is_valid, errors = stage.validate_input(current_data, context.artifacts)
            if not is_valid:
                raise ValueError(
                    f"Stage '{stage.stage_name}' input validation failed:\n" +
                    "\n".join(f"  - {err}" for err in errors)
                )

            # Execute stage
            try:
                result: StageResult = stage.process(current_data, context.artifacts)

                # Update current data for next stage
                current_data = result.data

                # Merge artifacts into context
                context.artifacts.update(result.artifacts)

                # Merge metadata
                context.metadata.update(result.metadata)

                # Accumulate metrics
                context.metrics.update(result.metrics)

                # Log stage completion
                if result.metrics:
                    metrics_str = ", ".join(f"{k}={v}" for k, v in result.metrics.items())
                    logger.info(f"[green]✔ Completed:[/] {stage.stage_name} ({metrics_str})")
                else:
                    logger.info(f"[green]✔ Completed:[/] {stage.stage_name}")

            except Exception as e:
                logger.error(f"[red]❌ Stage failed:[/] {stage.stage_name}")
                logger.error(f"[red]Error:[/] {e}")
                raise RuntimeError(f"Stage '{stage.stage_name}' failed: {e}") from e

        # Step 5: Return results
        logger.info("[bold green]🎉 Pipeline completed successfully![/]")
        logger.info(f"[green]Processed {context.metrics.get('total_messages', 0)} messages[/]")

        return {
            "status": "success",
            "metrics": context.metrics,
            "metadata": context.metadata,
            "artifacts": context.artifacts,
        }

    def __repr__(self) -> str:
        """String representation of the orchestrator."""
        return (
            f"CoreOrchestrator("
            f"adapter={self.source_adapter.source_identifier}, "
            f"stages={len(self.stages)})"
        )
