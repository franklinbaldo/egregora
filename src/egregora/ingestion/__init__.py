"""Ingestion stage - Parse input sources into structured data.

This package handles data extraction from various sources (WhatsApp, Slack, etc.),
converting them into Ibis tables for further processing.
"""

from egregora.ingestion.base import InputSource
from egregora.ingestion.parser import (
    extract_commands,
    filter_egregora_messages,
    parse_egregora_command,
    parse_export,
    parse_multiple,
)
from egregora.ingestion.slack_input import SlackInputSource
from egregora.ingestion.whatsapp_input import WhatsAppInputSource

__all__ = [
    "InputSource",
    "WhatsAppInputSource",
    "SlackInputSource",
    "parse_export",
    "parse_multiple",
    "extract_commands",
    "filter_egregora_messages",
    "parse_egregora_command",
]
