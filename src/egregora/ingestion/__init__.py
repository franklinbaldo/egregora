"""Ingestion stage - Parse input sources into structured data.

This package handles data extraction from various sources (WhatsApp, Slack, etc.),
converting them into Ibis tables for further processing.

Phase 6: WhatsApp-specific parsing moved to sources/whatsapp/
Backward compatibility maintained via re-exports.
"""

from egregora.ingestion.base import InputSource
from egregora.ingestion.slack_input import SlackInputSource

# Phase 6: Re-export WhatsApp parser for backward compatibility
# Actual implementation moved to sources/whatsapp/parser.py
from egregora.sources.whatsapp.input import WhatsAppInputSource
from egregora.sources.whatsapp.parser import (
    extract_commands,
    filter_egregora_messages,
    parse_egregora_command,
    parse_export,
    parse_multiple,
)

__all__ = [
    "InputSource",
    "SlackInputSource",
    "WhatsAppInputSource",
    "extract_commands",
    "filter_egregora_messages",
    "parse_egregora_command",
    "parse_export",
    "parse_multiple",
]
