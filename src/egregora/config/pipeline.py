"""Configuration dataclasses for pipeline operations.

This module extends the existing config/types.py with additional structured
configuration objects to reduce parameter counts in pipeline functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PipelineEnrichmentConfig:
    """Extended enrichment configuration for pipeline operations.

    This extends the basic EnrichmentConfig from types.py with additional
    pipeline-specific settings like batching and limits.

    Attributes:
        batch_threshold: Minimum items before batching API calls
        max_enrichments: Maximum number of enrichments per period
        enable_url: Whether to enrich URLs found in messages
        enable_media: Whether to enrich media attachments

    """

    batch_threshold: int = 10
    max_enrichments: int = 500
    enable_url: bool = True
    enable_media: bool = True

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.batch_threshold < 1:
            msg = f"batch_threshold must be >= 1, got {self.batch_threshold}"
            raise ValueError(msg)
        if self.max_enrichments < 0:
            msg = f"max_enrichments must be >= 0, got {self.max_enrichments}"
            raise ValueError(msg)

    @classmethod
    def from_cli_args(cls, **kwargs: Any) -> PipelineEnrichmentConfig:
        """Create config from CLI arguments."""
        return cls(
            batch_threshold=kwargs.get("batch_threshold", 10),
            max_enrichments=kwargs.get("max_enrichments", 500),
            enable_url=kwargs.get("enable_url", True),
            enable_media=kwargs.get("enable_media", True),
        )
