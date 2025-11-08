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

**Pipeline Stage Abstraction**:
  - `PipelineStage`, `StageConfig`, `StageResult`: Stage abstraction layer

**Source Adapters**:
  - `SourceAdapter`: Abstract interface for parsing different message sources
  - `MediaMapping`: Media attachment handling (WhatsApp, Slack, etc.)

**Intermediate Representation (IR)**:
  - `IR_SCHEMA`: Standardized schema all sources must produce (timestamp, author, message, etc.)
  - `create_ir_table`, `validate_ir_schema`: IR table utilities

**Windowing Utilities** (pipeline.py):
  - `create_windows`, `Window`: Message windowing (lazy-loaded)
  - `load_checkpoint`, `save_checkpoint`: Resume logic via sentinel files (lazy-loaded)

Architecture: Staged Pipeline
------------------------------

Egregora follows a **staged pipeline** with six phases (see CLAUDE.md for full diagram):

1. **Ingestion**: Parse WhatsApp/Slack exports → IR tables
2. **Privacy**: Anonymize PII → UUIDs (BEFORE any LLM processing)
3. **Augmentation**: LLM-powered enrichment (URLs, media, profiles)
4. **Knowledge**: RAG indexing, annotations, rankings
5. **Generation**: Pydantic-AI writer agent with tool calling
6. **Publication**: MkDocs site rendering

**Phase 7 Resume Logic**: Checkpoint-based resume using sentinel files.
Tracks last processed timestamp (not window indices). Post dates are LLM-decided.

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

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

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
# Windowing & Checkpoint Utilities Layer
# ============================================================================
# Lazy-loaded imports from pipeline.py module (windowing and checkpoint utilities).
# This __getattr__ hook provides transparent access to create_windows, Window,
# load_checkpoint, and save_checkpoint without requiring full module import.
# ============================================================================
# Run Tracking & Observability Layer
# ============================================================================
# Run tracking infrastructure for observability, lineage, and checkpointing.
# Re-exported from tracking.py for backwards compatibility.
from egregora.pipeline.tracking import (
    RunContext,
    fingerprint_table,
    get_git_commit_sha,
    record_lineage,
    record_run,
    run_stage_with_tracking,
)


def __getattr__(name: str) -> object:
    """Lazy import for windowing utilities from pipeline.py module.

    Dynamically loads windowing utilities (create_windows, checkpoints, etc.)
    from the egregora/pipeline.py module when accessed. This avoids circular
    imports and maintains a clean namespace.

    Args:
        name: Attribute name being accessed (e.g., 'create_windows')

    Returns:
        Requested attribute from pipeline.py module

    Raises:
        AttributeError: If attribute doesn't exist in the module

    """
    if name in (
        "create_windows",
        "Window",
        "load_checkpoint",
        "save_checkpoint",
        "split_window_into_n_parts",
    ):
        parent = sys.modules["egregora"]
        module_path = parent.__path__[0]
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
#   - Stage abstractions (PipelineStage, StageConfig, StageResult)
#   - Source adapters (SourceAdapter, MediaMapping)
#   - Windowing utilities (create_windows, Window - lazy-loaded via __getattr__)
#   - Checkpoint utilities (load_checkpoint, save_checkpoint - lazy-loaded via __getattr__)
#   - Run tracking (RunContext, record_run, run_stage_with_tracking)
__all__ = [
    "IR_SCHEMA",
    "MediaMapping",
    "PipelineStage",
    "RunContext",
    "SourceAdapter",
    "StageConfig",
    "StageResult",
    "Window",
    "create_ir_table",
    "create_windows",
    "fingerprint_table",
    "get_git_commit_sha",
    "load_checkpoint",
    "record_lineage",
    "record_run",
    "run_stage_with_tracking",
    "save_checkpoint",
    "split_window_into_n_parts",
    "validate_ir_schema",
]
