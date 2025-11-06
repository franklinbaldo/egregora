"""Core Pipeline Orchestrator - source-agnostic pipeline execution engine.

This module implements the main orchestration logic that runs pipeline stages
in sequence, managing checkpoints, context, and error handling. The orchestrator
is completely source-agnostic and works with any SourceAdapter implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from egregora.pipeline.ir import validate_ir_schema

if TYPE_CHECKING:
    from ibis.expr.types import Table

    from egregora.pipeline.adapters import MediaMapping, SourceAdapter
    from egregora.pipeline.base import PipelineStage, StageResult
__all__ = ["CoreOrchestrator", "PipelineArtifacts", "PipelineConfig", "PipelineContext"]
logger = logging.getLogger(__name__)


class PipelineArtifacts(TypedDict, total=False):
    """Type-safe definition of known pipeline artifacts.

    This TypedDict provides IDE autocomplete and type checking for commonly
    used artifacts while remaining extensible for stage-specific data.

    All fields are optional (total=False) to allow stages to add artifacts
    incrementally.

    Common Artifacts:
        media_mapping: Mapping from message media references to file paths
        group_slug: URL-safe identifier for the chat group/channel
        enrichment_cache: Cache object for enrichment results
        checkpoint_store: Checkpoint store for resumable processing
        period_tables: Grouped message tables by time period
        generated_posts: List of generated post file paths
        generated_profiles: List of generated profile file paths
    """

    media_mapping: MediaMapping
    group_slug: str
    group_name: str
    enrichment_cache: Any
    checkpoint_store: Any
    period_tables: dict[str, Table]
    current_period: str
    generated_posts: list[Path]
    generated_profiles: list[Path]
    rag_store: Any
    indexed_chunks: int


@dataclass
class PipelineContext:
    """Shared context passed between pipeline stages.

    This allows stages to share data and artifacts without tight coupling.
    Uses PipelineArtifacts TypedDict for type-safe common artifacts while
    remaining extensible for stage-specific data.
    """

    source_name: str
    input_path: Path
    output_dir: Path
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, int | float] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""

    input_path: Path
    output_dir: Path
    period: str = "day"
    timezone: str | None = None
    enable_enrichment: bool = True
    enable_rag: bool = True
    resume: bool = True
    checkpoint_dir: Path = Path(".egregora/checkpoints")
    batch_threshold: int = 10
    from_date: Any = None
    to_date: Any = None
    model_config: Any = None
    gemini_api_key: str | None = None
    client: Any = None
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None
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

    def __init__(self, source_adapter: SourceAdapter, stages: list[PipelineStage]) -> None:
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
        logger.info("[bold cyan]🚀 Starting pipeline:[/] %s", self.source_adapter.source_name)
        logger.info("[cyan]Input:[/] %s", config.input_path)
        logger.info("[cyan]Output:[/] %s", config.output_dir)
        context = PipelineContext(
            source_name=self.source_adapter.source_identifier,
            input_path=config.input_path,
            output_dir=config.output_dir,
        )
        logger.info("[bold cyan]📦 Parsing with adapter:[/] %s", self.source_adapter.source_name)
        messages_table = self.source_adapter.parse(config.input_path, timezone=config.timezone)
        is_valid, errors = validate_ir_schema(messages_table)
        if not is_valid:
            raise ValueError(
                "Source adapter produced invalid IR schema. Errors:\n"
                + "\n".join(f"  - {err}" for err in errors)
            )
        total_messages = messages_table.count().execute()
        logger.info("[green]✅ Parsed[/] %s messages", total_messages)
        context.metrics["total_messages"] = total_messages
        try:
            media_mapping = self.source_adapter.extract_media(config.input_path, config.output_dir)
            if media_mapping:
                logger.info("[green]📎 Extracted[/] %s media files", len(media_mapping))
                context.artifacts["media_mapping"] = media_mapping
        except NotImplementedError:
            logger.debug(
                "Source adapter %s does not support media extraction", self.source_adapter.source_name
            )
        try:
            metadata = self.source_adapter.get_metadata(config.input_path)
            context.metadata.update(metadata)
            if metadata:
                logger.info("[cyan]INFO Metadata:[/] %s", metadata)
        except Exception as e:
            logger.debug("Could not extract metadata: %s", e)
        current_data = messages_table
        for stage in self.stages:
            if not stage.config.enabled:
                logger.info("[yellow]⏭️  Skipping disabled stage:[/] %s", stage.stage_name)
                continue
            logger.info("[bold cyan]▶️  Running stage:[/] %s", stage.stage_name)
            is_valid, errors = stage.validate_input(current_data, context.artifacts)
            if not is_valid:
                raise ValueError(
                    f"Stage '{stage.stage_name}' input validation failed:\n"
                    + "\n".join(f"  - {err}" for err in errors)
                )
            try:
                result: StageResult = stage.process(current_data, context.artifacts)
                current_data = result.data
                context.artifacts.update(result.artifacts)
                context.metadata.update(result.metadata)
                context.metrics.update(result.metrics)
                if result.metrics:
                    metrics_str = ", ".join((f"{k}={v}" for k, v in result.metrics.items()))
                    logger.info("[green]✔ Completed:[/] %s (%s)", stage.stage_name, metrics_str)
                else:
                    logger.info("[green]✔ Completed:[/] %s", stage.stage_name)
            except Exception as e:
                logger.exception("[red]❌ Stage failed:[/] %s", stage.stage_name)
                logger.exception("[red]Error:[/] %s", e)
                msg = f"Stage '{stage.stage_name}' failed: {e}"
                raise RuntimeError(msg) from e
        logger.info("[bold green]🎉 Pipeline completed successfully![/]")
        logger.info("[green]Processed %s messages[/]", context.metrics.get("total_messages", 0))
        return {
            "status": "success",
            "metrics": context.metrics,
            "metadata": context.metadata,
            "artifacts": context.artifacts,
        }

    def __repr__(self) -> str:
        """String representation of the orchestrator."""
        return f"CoreOrchestrator(adapter={self.source_adapter.source_identifier}, stages={len(self.stages)})"
