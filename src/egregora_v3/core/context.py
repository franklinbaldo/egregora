"""Pipeline execution context for V3.

Provides request-scoped state without using globals."""
import uuid
from dataclasses import dataclass, field
from types import MappingProxyType
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
        """Ensure metadata is frozen (immutable)."""
        # Convert metadata dict to an immutable mapping to prevent mutation
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
