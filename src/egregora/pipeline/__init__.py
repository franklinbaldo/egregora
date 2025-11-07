"""Pipeline orchestration facade for Egregora's staged processing architecture.

This module serves as the main entry point for pipeline operations, providing a
clean facade over the modular components that power Egregora's message-to-blog
transformation. It exports core orchestration primitives, source adapters, and
utilities for building extensible, source-agnostic pipelines.

**Key Philosophy**: Egregora uses a **staged pipeline** (not traditional ETL) with
feedback loops and stateful operations. The architecture "trusts the LLM" - giving
AI agents full context and letting them make editorial decisions about post count,
themes, and structure.

What's Exported:
----------------

**Pipeline Orchestration**:
  - `CoreOrchestrator`: Main pipeline execution engine
  - `PipelineConfig`, `PipelineContext`, `PipelineArtifacts`: Configuration and state
  - `PipelineStage`, `StageConfig`, `StageResult`: Stage abstraction layer

**Source Adapters**:
  - `SourceAdapter`: Abstract interface for parsing different message sources
  - `MediaMapping`: Media attachment handling (WhatsApp, Slack, etc.)

**Intermediate Representation (IR)**:
  - `IR_SCHEMA`: Standardized schema all sources must produce (timestamp, author, message, etc.)
  - `create_ir_table`, `validate_ir_schema`: IR table utilities

**Backward Compatibility** (legacy pipeline.py):
  - `group_by_period`, `period_has_posts`: Temporal grouping utilities (lazy-loaded)

Architecture: Staged Pipeline
------------------------------

Egregora follows a **staged pipeline** with six phases (see CLAUDE.md for full diagram):

1. **Ingestion**: Parse WhatsApp/Slack exports → IR tables
2. **Privacy**: Anonymize PII → UUIDs (BEFORE any LLM processing)
3. **Augmentation**: LLM-powered enrichment (URLs, media, profiles)
4. **Knowledge**: RAG indexing, annotations, rankings
5. **Generation**: Pydantic-AI writer agent with tool calling
6. **Publication**: MkDocs site rendering

**Phase 3 Resume Logic**: Simple file existence checks (not complex checkpoints).
Stages can skip work if artifacts already exist (e.g., skip enrichment if cache hit).

Usage Example:
--------------

Basic pipeline execution flow::

    from egregora.pipeline import CoreOrchestrator, PipelineConfig
    from egregora.adapters.whatsapp import WhatsAppAdapter
    from egregora.pipeline.stages import PrivacyStage, EnrichmentStage, WritingStage

    # Configure pipeline with temporal grouping
    config = PipelineConfig(
        input_path=Path("export.zip"),
        output_dir=Path("output"),
        period="week",  # Group conversations by week
        enable_enrichment=True,
    )

    # Assemble staged pipeline
    adapter = WhatsAppAdapter()
    stages = [
        PrivacyStage(config),      # Anonymize BEFORE LLM processing
        EnrichmentStage(config),   # LLM-powered context (cached)
        WritingStage(config),      # Pydantic-AI agent with tools
    ]

    # Execute with feedback loops
    orchestrator = CoreOrchestrator(adapter, stages)
    result = orchestrator.run(config)  # Returns PipelineArtifacts

Pipeline Flow Diagram:
----------------------

::

    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  Ingestion  │ -> │   Privacy   │ -> │ Augmentation│
    └─────────────┘    └─────────────┘    └─────────────┘
          ↓                   ↓                   ↓
       Parse ZIP        Anonymize UUIDs     Enrich context
      (IR Schema)       Detect PII          Build profiles

    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  Knowledge  │ <- │ Generation  │ -> │Publication  │
    └─────────────┘    └─────────────┘    └─────────────┘
          ↑                   ↓                   ↓
       RAG Index        LLM Writer           MkDocs Site
       Annotations      Tool Calling         Templates
       Rankings

Notes
-----
- All pipeline stages operate on Ibis tables conforming to IR_SCHEMA
- Privacy stage MUST run before any LLM API calls (PII protection invariant)
- Stages are functional transformations: Table → Table
- Resume logic uses simple file existence checks, not complex state machines
- See CLAUDE.md for full architecture details and TENET-BREAK philosophy

"""

# ============================================================================
# Source Adapter Primitives
# ============================================================================
# Abstract interfaces for parsing different message sources (WhatsApp, Slack, etc.)
# and handling media attachments across platforms.
from egregora.pipeline.adapters import MediaMapping, SourceAdapter

# ============================================================================
# Pipeline Stage Abstraction
# ============================================================================
# Base classes for building modular, composable pipeline stages. Each stage
# implements the PipelineStage protocol: Table → Table transformations.
from egregora.pipeline.base import PipelineStage, StageConfig, StageResult

# ============================================================================
# Intermediate Representation (IR)
# ============================================================================
# Standardized schema that all source adapters must produce. Ensures uniform
# data structure across different chat platforms (timestamp, author, message, etc.).
from egregora.pipeline.ir import IR_SCHEMA, create_ir_table, validate_ir_schema

# ============================================================================
# Core Orchestrator
# ============================================================================
# Main pipeline execution engine that coordinates source adapters, stages, and
# state management. Handles configuration, context propagation, and artifact collection.
from egregora.pipeline.orchestrator import (
    CoreOrchestrator,
    PipelineArtifacts,
    PipelineConfig,
    PipelineContext,
)

# ============================================================================
# Backward Compatibility Layer
# ============================================================================
# Lazy-loaded imports from legacy pipeline.py module (temporal grouping utilities).
# This __getattr__ hook provides transparent access to group_by_period and
# period_has_posts without requiring full module import. Enables gradual migration
# from monolithic pipeline.py to modular pipeline/ package structure.


def __getattr__(name: str) -> object:
    """Lazy import for backward compatibility with pipeline.py module.

    Dynamically loads temporal grouping utilities (group_by_period, period_has_posts)
    from the legacy egregora/pipeline.py module when accessed. This avoids circular
    imports and maintains API compatibility during the transition to the new
    pipeline package architecture.

    Args:
        name: Attribute name being accessed (e.g., 'group_by_period')

    Returns:
        Requested attribute from pipeline.py module

    Raises:
        AttributeError: If attribute doesn't exist in backward compat layer

    """
    if name in ("group_by_period", "period_has_posts"):
        import sys

        parent = sys.modules["egregora"]
        module_path = parent.__path__[0]
        from importlib.util import module_from_spec, spec_from_file_location
        from pathlib import Path

        pipeline_py = Path(module_path) / "pipeline.py"
        spec = spec_from_file_location("egregora._pipeline_utils", pipeline_py)
        if spec and spec.loader:
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


# ============================================================================
# Public API Exports
# ============================================================================
# Explicit export list for clean namespace. Groups exports by category:
#   - IR primitives (IR_SCHEMA, create_ir_table, validate_ir_schema)
#   - Orchestration (CoreOrchestrator, PipelineConfig, PipelineContext, PipelineArtifacts)
#   - Stage abstractions (PipelineStage, StageConfig, StageResult)
#   - Source adapters (SourceAdapter, MediaMapping)
#   - Backward compat (group_by_period, period_has_posts - lazy-loaded via __getattr__)
__all__ = [
    "IR_SCHEMA",
    "CoreOrchestrator",
    "MediaMapping",
    "PipelineArtifacts",
    "PipelineConfig",
    "PipelineContext",
    "PipelineStage",
    "SourceAdapter",
    "StageConfig",
    "StageResult",
    "create_ir_table",
    "group_by_period",
    "period_has_posts",
    "validate_ir_schema",
]
