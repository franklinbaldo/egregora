"""Concrete pipeline stage implementations.

This package contains specific stage implementations that perform the actual
work of the pipeline: filtering, enrichment, writing, RAG indexing, etc.

Each stage is a standalone module that implements the PipelineStage interface.

Stage Registry:
--------------
Use STAGE_REGISTRY to discover available stages dynamically:

    >>> from egregora.pipeline.stages import get_stage, STAGE_REGISTRY
    >>> print(STAGE_REGISTRY.keys())
    dict_keys(['filtering'])
    >>> stage = get_stage('filtering', config)
"""

from egregora.pipeline.base import PipelineStage, StageConfig
from egregora.pipeline.stages.filtering import FilteringStage, FilteringStageConfig

STAGE_REGISTRY: dict[str, type[PipelineStage]] = {"filtering": FilteringStage}


def get_stage(stage_identifier: str, config: StageConfig) -> PipelineStage:
    """Get a stage instance by identifier.

    Args:
        stage_identifier: Stage identifier (e.g., "filtering", "enrichment")
        config: Stage configuration

    Returns:
        Initialized stage instance

    Raises:
        ValueError: If stage identifier is not recognized

    Example:
        >>> from egregora.pipeline.stages import get_stage
        >>> from egregora.pipeline.stages.filtering import FilteringStageConfig
        >>> config = FilteringStageConfig(enabled=True)
        >>> stage = get_stage("filtering", config)
        >>> stage.stage_name
        'Message Filtering'

    """
    if stage_identifier not in STAGE_REGISTRY:
        available = ", ".join(STAGE_REGISTRY.keys())
        msg = f"Unknown stage: '{stage_identifier}'. Available stages: {available}"
        raise ValueError(msg)
    stage_class = STAGE_REGISTRY[stage_identifier]
    return stage_class(config)


def list_stages() -> list[str]:
    """List all available stage identifiers.

    Returns:
        List of stage identifiers

    Example:
        >>> from egregora.pipeline.stages import list_stages
        >>> list_stages()
        ['filtering']

    """
    return list(STAGE_REGISTRY.keys())


__all__ = ["STAGE_REGISTRY", "FilteringStage", "FilteringStageConfig", "get_stage", "list_stages"]
