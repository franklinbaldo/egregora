"""Concrete pipeline stage implementations.

This package contains specific stage implementations that perform the actual
work of the pipeline: filtering, enrichment, writing, RAG indexing, etc.

Each stage is a standalone module that implements the PipelineStage interface.
"""

from egregora.pipeline.stages.filtering import FilteringStage, FilteringStageConfig

__all__ = [
    "FilteringStage",
    "FilteringStageConfig",
]
