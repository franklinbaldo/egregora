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


# Gemini model context limits (input tokens)
# Source: https://ai.google.dev/gemini-api/docs/models/gemini
KNOWN_MODEL_LIMITS = {
    # Gemini 2.0 family
    "gemini-2.0-flash-exp": 1_048_576,  # 1M tokens
    "gemini-2.0-flash-thinking-exp": 32_768,  # 32k tokens (experimental thinking mode)
    # Gemini 1.5 family
    "gemini-1.5-flash": 1_048_576,  # 1M tokens
    "gemini-1.5-flash-8b": 1_048_576,  # 1M tokens
    "gemini-1.5-flash-latest": 1_048_576,  # 1M tokens
    "gemini-1.5-pro": 2_097_152,  # 2M tokens
    "gemini-1.5-pro-latest": 2_097_152,  # 2M tokens
    # Gemini 1.0 family (older, smaller limits)
    "gemini-pro": 32_768,  # 32k tokens
    "gemini-1.0-pro": 32_768,  # 32k tokens
    # Embeddings
    "text-embedding-004": 2048,  # 2k tokens (for embeddings, not generation)
}


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


class AuthorPrivacyStrategy(str, Enum):
    """How to handle author identification in structural anonymization."""

    UUID_MAPPING = "uuid_mapping"  # Alice → 550e8400-e29b-41d4-a716...
    FULL_REDACTION = "full_redaction"  # Alice → [AUTHOR]
    ROLE_BASED = "role_based"  # Alice → Participant_1
    NONE = "none"  # Alice → Alice (public data)


class MentionPrivacyStrategy(str, Enum):
    """How to handle @mentions in text during structural preprocessing."""

    UUID_REPLACEMENT = "uuid_replacement"  # @Alice → @550e8400...
    GENERIC_REDACTION = "generic_redaction"  # @Alice → @[MENTION]
    ROLE_BASED = "role_based"  # @Alice → @Participant_1
    NONE = "none"  # @Alice → @Alice


class TextPIIStrategy(str, Enum):
    """How to handle PII in raw text during structural preprocessing.

    Note: These strategies are for INPUT preprocessing only (deterministic).
    LLM outputs use natural language instructions, not regex patterns.
    """

    REDACT = "redact"  # 555-1234 → [PHONE] (deterministic)
    HASH = "hash"  # 555-1234 → PHONE_a3f8b9 (deterministic)
    NONE = "none"  # 555-1234 → 555-1234 (public data)


class PIIScope(str, Enum):
    """What PII to protect in LLM outputs (LLM-native understanding).

    LLMs naturally understand what constitutes PII without regex patterns.
    These scopes tell the LLM what we consider private.
    """

    CONTACT_INFO = "contact_info"  # Phone, email, address, personal URLs
    ALL_PII = "all_pii"  # Contact + names, ages, locations, identifiers
    CUSTOM = "custom"  # User-defined specification (LLM interprets)
    LLM_DECIDE = "llm_decide"  # Let LLM use its judgment
