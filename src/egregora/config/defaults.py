"""Centralized defaults for Egregora configuration.

This module provides a single source of truth for default values,
magic numbers, and standard configurations.
"""

from dataclasses import dataclass

from egregora.constants import WindowUnit


@dataclass(frozen=True)
class PipelineDefaults:
    """Pipeline processing defaults."""

    MAX_PROMPT_TOKENS: int = 400_000
    """Maximum tokens per prompt before auto-splitting."""

    PROACTIVE_SPLIT_THRESHOLD: float = 0.8
    """Threshold for proactive splitting (80% of max)."""

    PROACTIVE_SPLIT_DIVISOR: int = 5
    """Divisor for proactive split calculation."""

    STEP_SIZE: int = 100
    """Default window step size."""

    STEP_UNIT: WindowUnit = WindowUnit.MESSAGES
    """Default window step unit."""

    OVERLAP_RATIO: float = 0.2
    """Overlap ratio between consecutive windows."""

    AVG_TOKENS_PER_MESSAGE: int = 5
    """Average tokens per message for window size estimation."""

    BUFFER_RATIO: float = 0.8
    """Buffer ratio for window size estimation."""

    DEFAULT_FROM_DATE: str | None = None
    DEFAULT_TO_DATE: str | None = None
    DEFAULT_TIMEZONE: str | None = None
    DEFAULT_USE_FULL_CONTEXT: bool = False
    DEFAULT_MAX_WINDOWS: int | None = None
    DEFAULT_RESUME: bool = True


@dataclass(frozen=True)
class ModelDefaults:
    """AI model defaults."""

    WRITER: str = "google-gla:gemini-2.5-flash"
    """Default model for Writer agent."""

    READER: str = "google-gla:gemini-2.5-flash"
    """Default model for Reader agent."""

    ENRICHER: str = "google-gla:gemini-2.5-flash"
    """Default model for Enrichment agent."""

    ENRICHER_VISION: str = "google-gla:gemini-2.5-flash"
    """Default model for Vision Enrichment agent."""

    RANKING: str = "google-gla:gemini-2.5-flash"
    """Default model for Ranking."""

    EDITOR: str = "google-gla:gemini-2.5-flash"
    """Default model for Editor."""

    EMBEDDING: str = "models/gemini-embedding-001"
    """Default embedding model for RAG."""

    BANNER: str = "models/gemini-2.5-flash"
    """Default banner generation model."""


@dataclass(frozen=True)
class RateLimitDefaults:
    """Rate limiting defaults."""

    REQUESTS_PER_SECOND: float = 2.0
    """Maximum requests per second to LLM APIs."""

    BURST_SIZE: int = 5
    """Maximum burst size for rate limiting."""

    CONCURRENCY: int = 5
    """Maximum number of concurrent tasks."""

    DAILY_REQUESTS: int = 100
    """Soft limit for daily LLM calls."""


# Global Constants
EMBEDDING_DIM = 768
DEFAULT_SITE_NAME = "default"
DEFAULT_PIPELINE_DB = "duckdb:///./.egregora/pipeline.duckdb"
DEFAULT_READER_DB = ".egregora/reader.duckdb"
RAG_TOP_K_WARNING_THRESHOLD = 20
MAX_PROMPT_TOKENS_WARNING_THRESHOLD = 200_000
