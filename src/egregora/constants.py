"""Central location for all constants used throughout the application.

This module provides type-safe constants using enums to replace magic strings
and numbers scattered throughout the codebase.
"""

from enum import Enum


class EgregoraCommand(str, Enum):
    """User commands recognized by the system."""

    OPT_OUT = "/egregora opt-out"
    OPT_IN = "/egregora opt-in"
    HELP = "/egregora help"
    STATUS = "/egregora status"


class PluginType(str, Enum):
    """Available plugin types."""

    BLOG = "blog"
    FORUM = "forum"
    WIKI = "wiki"


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


class FileFormat(str, Enum):
    """Supported file formats and extensions."""

    PARQUET = ".parquet"
    CSV = ".csv"
    JSON = ".json"
    DUCKDB = ".duckdb"
    MARKDOWN = ".md"


class IndexType(str, Enum):
    """Vector index types for database."""

    HNSW = "HNSW"
    FLAT = "FLAT"


class RetrievalMode(str, Enum):
    """RAG retrieval modes."""

    ANN = "ann"
    EXACT = "exact"


class SourceType(str, Enum):
    """Input source types for data ingestion."""

    WHATSAPP = "whatsapp"
    IPERON_TJRO = "iperon-tjro"
    SELF_REFLECTION = "self"


class WindowUnit(str, Enum):
    """Units for windowing messages."""

    MESSAGES = "messages"
    HOURS = "hours"
    DAYS = "days"
    BYTES = "bytes"


class MediaType(str, Enum):
    """Media content types."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class Limits:
    """Numeric limits and thresholds used throughout the system.

    These are class attributes (not enum) since they may need to be
    overridden by configuration or environment variables.
    """

    MAX_ENRICHMENTS_DEFAULT = 500
    BATCH_THRESHOLD_DEFAULT = 10
    MAX_URLS_PER_MESSAGE = 3
    MAX_MEDIA_PER_MESSAGE = 5
    RAG_DEFAULT_TOP_K = 10
    RAG_DEFAULT_OVERFETCH = 5
    SINGLE_DIGIT_THRESHOLD = 10
    DEFAULT_REQUEST_TIMEOUT = 30
    LONG_REQUEST_TIMEOUT = 120


class SystemIdentifier(str, Enum):
    """Special system identifiers used for generated content."""

    EGREGORA_AUTHOR = "egregora"
    ANONYMOUS_USER = "anonymous"


class OutputAdapter(str, Enum):
    """Output format options for data export."""

    TABLE = "table"
    JSON = "json"
    PARQUET = "parquet"
    CSV = "csv"
