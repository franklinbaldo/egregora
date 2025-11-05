"""Core pipeline infrastructure for source-agnostic message processing.

This package provides the foundational components for building a modular,
extensible pipeline that can process messages from any source (WhatsApp,
Slack, Discord, etc.) through a standardized set of stages.

Key Components:
---------------

1. **Intermediate Representation (IR)**
   - Standardized schema that all sources must produce
   - See: pipeline.ir

2. **Source Adapters**
   - Abstract interface for parsing different sources
   - See: pipeline.adapters.SourceAdapter

3. **Pipeline Stages**
   - Modular transformation steps
   - See: pipeline.stages.PipelineStage

4. **Core Orchestrator**
   - Source-agnostic execution engine
   - See: pipeline.orchestrator.CoreOrchestrator

Usage Example:
--------------

    from egregora.pipeline import CoreOrchestrator, PipelineConfig
    from egregora.adapters.whatsapp import WhatsAppAdapter
    from egregora.pipeline.stages import (
        FilteringStage,
        EnrichmentStage,
        WritingStage,
    )

    # Configure pipeline
    config = PipelineConfig(
        input_path=Path("export.zip"),
        output_dir=Path("output"),
        period="day",
        enable_enrichment=True,
    )

    # Set up adapter and stages
    adapter = WhatsAppAdapter()
    stages = [
        FilteringStage(config),
        EnrichmentStage(config),
        WritingStage(config),
    ]

    # Run pipeline
    orchestrator = CoreOrchestrator(adapter, stages)
    result = orchestrator.run(config)

Architecture:
-------------

    Raw Export (ZIP/JSON/etc.)
            ↓
    [Source Adapter] → parse() → Intermediate Representation (IR)
            ↓
    [Pipeline Stage 1] → Filtering
            ↓
    [Pipeline Stage 2] → Enrichment
            ↓
    [Pipeline Stage 3] → Writing
            ↓
    Output (Posts, Profiles, etc.)
"""

from egregora.pipeline.adapters import MediaMapping, SourceAdapter
from egregora.pipeline.base import PipelineStage, StageConfig, StageResult
from egregora.pipeline.ir import IR_SCHEMA, create_ir_table, validate_ir_schema
from egregora.pipeline.orchestrator import CoreOrchestrator, PipelineConfig, PipelineContext

# Note: group_by_period is in the parent egregora.pipeline module (pipeline.py)
# It will be imported directly from there when needed
# We don't re-export it here to avoid circular imports

__all__ = [
    # IR Schema
    "IR_SCHEMA",
    "validate_ir_schema",
    "create_ir_table",
    # Adapters
    "SourceAdapter",
    "MediaMapping",
    # Stages
    "PipelineStage",
    "StageConfig",
    "StageResult",
    # Orchestrator
    "CoreOrchestrator",
    "PipelineConfig",
    "PipelineContext",
]
