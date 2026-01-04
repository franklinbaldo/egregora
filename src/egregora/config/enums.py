"""Configuration-specific enumerations."""
from enum import Enum


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
