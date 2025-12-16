"""Central location for all constants used throughout the application.

This module provides type-safe constants using enums to replace magic strings
and numbers scattered throughout the codebase.
"""

from enum import Enum


class SourceType(str, Enum):
    """Input source types for data ingestion."""

    WHATSAPP = "whatsapp"


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

# Egregora system author constants
# Used when Egregora generates content (PROFILE posts, ANNOUNCEMENT posts)
EGREGORA_UUID = "00000000-0000-0000-0000-000000000000"
EGREGORA_NAME = "Egregora"
