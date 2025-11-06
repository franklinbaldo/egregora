"""Central location for all constants used throughout the application.

This module provides type-safe constants using enums to replace magic strings
and numbers scattered throughout the codebase.
"""

from enum import Enum

# ============================================================================
# Commands
# ============================================================================


class EgregoraCommand(str, Enum):
    """User commands recognized by the system."""

    OPT_OUT = "/egregora opt-out"
    OPT_IN = "/egregora opt-in"
    HELP = "/egregora help"
    STATUS = "/egregora status"


# ============================================================================
# Plugins
# ============================================================================


class PluginType(str, Enum):
    """Available plugin types."""

    BLOG = "blog"
    FORUM = "forum"
    WIKI = "wiki"


# ============================================================================
# Pipeline Steps & Status
# ============================================================================


class PipelineStep(str, Enum):
    """Pipeline step names."""

    ENRICHMENT = "enrichment"
    WRITING = "writing"
    PROFILES = "profiles"
    RAG = "rag"


class StepStatus(str, Enum):
    """Pipeline step statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# File Formats
# ============================================================================


class FileFormat(str, Enum):
    """Supported file formats and extensions."""

    PARQUET = ".parquet"
    CSV = ".csv"
    JSON = ".json"
    DUCKDB = ".duckdb"
    MARKDOWN = ".md"


# ============================================================================
# Database
# ============================================================================


class IndexType(str, Enum):
    """Vector index types for database."""

    HNSW = "HNSW"  # Hierarchical Navigable Small World
    FLAT = "FLAT"  # Exhaustive search


class RetrievalMode(str, Enum):
    """RAG retrieval modes."""

    ANN = "ann"  # Approximate Nearest Neighbor
    FLAT = "flat"  # Exhaustive search


# ============================================================================
# Time Periods
# ============================================================================


class TimePeriod(str, Enum):
    """Time period groupings for conversations."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


# ============================================================================
# Media Types
# ============================================================================


class MediaType(str, Enum):
    """Media content types."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


# ============================================================================
# Numeric Limits & Thresholds
# ============================================================================


class Limits:
    """Numeric limits and thresholds used throughout the system.

    These are class attributes (not enum) since they may need to be
    overridden by configuration or environment variables.
    """

    # Enrichment limits
    MAX_ENRICHMENTS_DEFAULT = 500
    BATCH_THRESHOLD_DEFAULT = 10
    MAX_URLS_PER_MESSAGE = 3
    MAX_MEDIA_PER_MESSAGE = 5

    # RAG limits
    RAG_DEFAULT_TOP_K = 10
    RAG_DEFAULT_OVERFETCH = 5

    # Display thresholds
    SINGLE_DIGIT_THRESHOLD = 10  # When to pad numbers with leading zeros

    # Timeout values (seconds)
    DEFAULT_REQUEST_TIMEOUT = 30
    LONG_REQUEST_TIMEOUT = 120


# ============================================================================
# System Identifiers
# ============================================================================


class SystemIdentifier(str, Enum):
    """Special system identifiers used for generated content."""

    EGREGORA_AUTHOR = "egregora"  # Author name for enrichment messages
    ANONYMOUS_USER = "anonymous"  # Placeholder for anonymized users


# ============================================================================
# Export Formats
# ============================================================================


class OutputFormat(str, Enum):
    """Output format options for data export."""

    TABLE = "table"
    JSON = "json"
    PARQUET = "parquet"
    CSV = "csv"
