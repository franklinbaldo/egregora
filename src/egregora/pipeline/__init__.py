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
from egregora.pipeline.orchestrator import (
    CoreOrchestrator,
    PipelineArtifacts,
    PipelineConfig,
    PipelineContext,
)


# Import utilities from pipeline.py module for backward compatibility
# Use __getattr__ to avoid circular import during module initialization
def __getattr__(name):
    """Lazy import for backward compatibility with pipeline.py module."""
    if name in ("group_by_period", "period_has_posts"):
        # Import the module-level pipeline.py file (not this package)
        import sys
        from importlib import import_module

        # Get the parent module to access pipeline.py sibling
        parent = sys.modules["egregora"]
        module_path = parent.__path__[0]

        # Import pipeline.py using spec_from_file_location to avoid name collision
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


__all__ = [
    # IR Schema
    "IR_SCHEMA",
    # Orchestrator
    "CoreOrchestrator",
    "MediaMapping",
    "PipelineArtifacts",
    "PipelineConfig",
    "PipelineContext",
    # Stages
    "PipelineStage",
    # Adapters
    "SourceAdapter",
    "StageConfig",
    "StageResult",
    "create_ir_table",
    # Utilities (from pipeline.py module)
    "group_by_period",
    "period_has_posts",
    "validate_ir_schema",
]
