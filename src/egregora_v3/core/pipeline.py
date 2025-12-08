from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from egregora_v3.core.config import EgregoraConfig


class PipelineContext(BaseModel):
    """Request-scoped state for the pipeline.

    Used as the RunContext in Pydantic-AI agents.
    Provides access to configuration, infrastructure, and runtime state.
    """

    # Runtime Identity
    run_id: UUID = Field(default_factory=uuid4, description="Unique ID for this pipeline execution")

    # Configuration
    config: EgregoraConfig = Field(..., description="Application configuration")
    dry_run: bool = Field(default=False, description="If True, skip side-effecting operations (writes)")

    # Infrastructure Ports (Optional - may be injected or resolved)
    # Using 'Any' temporarily if types aren't fully available/circular import,
    # but preferably specific Protocols.
    # Note: Pydantic-AI Context often carries dependencies.
    # For now, we'll keep it simple data container.

    model_config = {"arbitrary_types_allowed": True}
