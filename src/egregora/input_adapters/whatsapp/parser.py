"""WhatsApp chat parser that converts ZIP exports to Ibis Tables.

This module handles parsing of WhatsApp export files into structured data.
It automatically anonymizes all author names before returning data.

MODERN (Phase 8): Pure Ibis/DuckDB parsing without pyparsing dependency.
Uses vectorized string operations and regex instead of pyparsing grammar.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

# Import command-related functions from the new, dedicated module.
from egregora.input_adapters.whatsapp.commands import (
    extract_commands,
    filter_egregora_messages,
    parse_egregora_command,
)
from egregora.input_adapters.whatsapp.parser_sql import parse_multiple as _parse_multiple_impl
from egregora.input_adapters.whatsapp.parser_sql import parse_source as _parse_source_impl

if TYPE_CHECKING:
    from collections.abc import Sequence
    from zoneinfo import ZoneInfo

    from ibis.expr.types import Table

    from egregora.input_adapters.whatsapp.models import WhatsAppExport

logger = logging.getLogger(__name__)


def parse_source(
    export: WhatsAppExport,
    timezone: str | ZoneInfo | None = None,
    *,
    expose_raw_author: bool = False,
) -> Table:
    """Parse an individual WhatsApp export into an Ibis Table."""
    return _parse_source_impl(export, timezone=timezone, expose_raw_author=expose_raw_author)


def parse_multiple(
    exports: Sequence[WhatsAppExport],
    timezone: str | ZoneInfo | None = None,
    *,
    expose_raw_author: bool = False,
) -> Table:
    """Parse multiple exports and concatenate them ordered by timestamp."""
    return _parse_multiple_impl(
        exports,
        timezone=timezone,
        expose_raw_author=expose_raw_author,
    )


__all__ = [
    "extract_commands",
    "filter_egregora_messages",
    "parse_egregora_command",
    "parse_multiple",
    "parse_source",
]
