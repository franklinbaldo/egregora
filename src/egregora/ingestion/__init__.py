"""Ingestion stage - Parse WhatsApp exports into structured data.

This package handles the initial data extraction from WhatsApp ZIP exports,
converting them into Ibis tables for further processing.
"""

from egregora.ingestion.parser import (
    extract_commands,
    filter_egregora_messages,
    parse_egregora_command,
    parse_export,
    parse_multiple,
)

__all__ = [
    "parse_export",
    "parse_multiple",
    "extract_commands",
    "filter_egregora_messages",
    "parse_egregora_command",
]
