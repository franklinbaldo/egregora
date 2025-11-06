"""Pipeline Stage abstraction for modular, testable processing.

This module defines the abstract interface for pipeline stages and provides
base implementations for common stage patterns. Each stage transforms data
in a specific way and can optionally support checkpointing and caching.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ibis.expr.types import Table
__all__ = ["PipelineStage", "StageConfig", "StageResult"]


@dataclass
class StageConfig:
    """Configuration for a pipeline stage.

    Common configuration options shared across all stages.
    Individual stages may extend this with stage-specific options.
    """

    enabled: bool = True
    cache_enabled: bool = False
    cache_dir: Path = Path(".egregora-cache")
    checkpoint_enabled: bool = False
    checkpoint_dir: Path = Path(".egregora/checkpoints")
    max_retries: int = 3
    timeout_seconds: int | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """Result of a pipeline stage execution.

    Contains the transformed data plus metadata about the execution.
    """

    data: Table
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    modified: bool = True
    metrics: dict[str, int | float] = field(default_factory=dict)


class PipelineStage(ABC):
    """Abstract base class for all pipeline stages.

    A pipeline stage is a discrete transformation step that:
    1. Takes an Ibis Table as input
    2. Performs a specific transformation
    3. Returns a StageResult with the transformed Table

    Stages can optionally support:
    - Checkpointing (for long-running operations that can be resumed)
    - Caching (for expensive operations with deterministic outputs)
    - Error handling and retries
    """

    def __init__(self, config: StageConfig) -> None:
        """Initialize the stage with configuration.

        Args:
            config: Stage configuration

        """
        self.config = config

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Return the human-readable name of this stage.

        Used for logging and debugging.
        Examples: "Message Filtering", "URL Enrichment", "Post Writing"
        """

    @property
    @abstractmethod
    def stage_identifier(self) -> str:
        """Return the unique identifier for this stage.

        Used for checkpoints and configuration.
        Examples: "filtering", "enrichment", "writing"
        """

    @abstractmethod
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        """Execute the stage transformation.

        This is the core method that performs the stage's work.

        Args:
            data: Input Ibis Table (typically IR-compliant messages)
            context: Shared pipeline context with artifacts from previous stages
                    Examples: {"media_mapping": {...}, "group_slug": "my-group"}

        Returns:
            StageResult with transformed data and metadata

        Raises:
            ValueError: If input data is invalid
            RuntimeError: If stage execution fails

        """

    def supports_checkpointing(self) -> bool:
        """Whether this stage supports checkpointing for resume capability.

        Override this to return True for long-running stages (enrichment, writing).
        """
        return False

    def supports_caching(self) -> bool:
        """Whether this stage's output can be cached.

        Override this to return True for expensive, deterministic operations.
        """
        return False

    def validate_input(self, _data: Table, _context: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate input data before processing (optional).

        Args:
            data: Input table to validate
            context: Pipeline context

        Returns:
            Tuple of (is_valid, list_of_errors)

        Note:
            Default implementation returns (True, []) (no validation).
            Override to add custom validation logic.

        """
        return (True, [])

    def __repr__(self) -> str:
        """String representation of the stage."""
        return f"{self.__class__.__name__}(identifier='{self.stage_identifier}')"
