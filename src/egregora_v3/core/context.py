"""Pipeline execution context for V3.

PipelineContext carries request-scoped state through the pipeline
without using global variables.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from egregora_v3.core.config import EgregoraConfig


@dataclass(frozen=True)
class PipelineContext:
    """Request-scoped context for pipeline execution.

    Carries configuration, run metadata, and dependencies through
    the agent pipeline without global state.

    Attributes:
        run_id: Unique identifier for this pipeline run
        config: Egregora configuration (optional)
        workspace_id: Workspace identifier (optional, for multi-workspace)
        metadata: Additional run metadata (frozen dict)

    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: EgregoraConfig | None = None
    workspace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure metadata is copied to avoid external mutation."""
        # Use object.__setattr__ since dataclass is frozen
        # We copy the dict to ensure the context holds its own version
        object.__setattr__(self, "metadata", dict(self.metadata))
