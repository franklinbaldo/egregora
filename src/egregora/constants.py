"""Central location for all constants used throughout the application.

This module provides type-safe constants using enums to replace magic strings
and numbers scattered throughout the codebase.
"""

from enum import Enum


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


# Egregora system author constants
# Used when Egregora generates content (PROFILE posts, ANNOUNCEMENT posts)
EGREGORA_UUID = "00000000-0000-0000-0000-000000000000"
AVATAR_NAMESPACE_UUID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"  # uuid.NAMESPACE_DNS
EGREGORA_NAME = "Egregora"

# Namespace UUID for generating deterministic avatar IDs (v5)
AVATAR_NAMESPACE_UUID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"

# Profile history context settings
# Maximum number of recent profile posts to include in LLM context window


class OutputAdapter(str, Enum):
    """Output format options for data export."""

    TABLE = "table"
    JSON = "json"
    PARQUET = "parquet"
    CSV = "csv"
