"""Ingestion stage - Generic interfaces and base classes for parsing input sources.

**Purpose:**
This package defines the generic interfaces and abstractions for ingesting data from
various chat platforms (WhatsApp, Slack, Discord, etc.). It provides:

- `InputSource`: Abstract base class defining the parsing contract
- `InputMetadata`: Standardized metadata about input sources
- `InputSourceRegistry`: Registry for auto-detecting and managing source parsers

**Relationship to `sources/`:**
The `sources/` module contains platform-specific implementations that implement the
`InputSource` interface. This separation follows the Interface Segregation Principle:
- `ingestion/` = Generic interfaces and base classes (this package)
- `sources/` = Concrete implementations (e.g., `sources/whatsapp/`, `sources/slack/`)

**Phase 6 Refactoring:**
WhatsApp-specific parsing was moved to `sources/whatsapp/parser.py`. This package
re-exports those functions for backward compatibility (facade pattern).

**Re-exports:**
This module re-exports commonly used parsers and utilities:
- `WhatsAppInputSource` from `sources/whatsapp/input.py`
- `parse_source()` and related functions from `sources/whatsapp/parser.py`
- `SlackInputSource` from `ingestion/slack_input.py` (legacy, needs Phase 6 migration)

**Example Usage:**

Using the InputSource abstraction directly:

    >>> from pathlib import Path
    >>> from egregora.ingestion import WhatsAppInputSource
    >>>
    >>> source = WhatsAppInputSource()
    >>> messages_table, metadata = source.parse(Path("export.zip"))
    >>>
    >>> print(f"Parsed {len(messages_table)} messages from {metadata.group_name}")
    >>> print(f"Source type: {metadata.source_type}")

Using the convenience function (backward compatible):

    >>> from egregora.ingestion import parse_source
    >>>
    >>> table = parse_source(Path("export.zip"))
    >>> print(table.schema())  # Conforms to MESSAGE_SCHEMA

Auto-detecting source type:

    >>> from egregora.ingestion.base import input_registry
    >>>
    >>> source = input_registry.detect_source(Path("export.zip"))
    >>> if source:
    ...     messages, meta = source.parse(Path("export.zip"))
    ...     print(f"Detected {source.source_type} export")

**Architecture:**
All parsers must return Ibis Tables conforming to MESSAGE_SCHEMA:
- timestamp: datetime (timezone-aware)
- date: date (local date)
- author: string (real names, anonymized later in privacy stage)
- message: string (plain text or markdown)
- original_line: string (raw input for debugging)
- tagged_line: string (can be same as message initially)
- message_id: string (deterministic, unique identifier)

See Also:
    - `sources/` - Platform-specific implementations
    - `database/schema.py` - MESSAGE_SCHEMA definition
    - `ingestion/base.py` - InputSource interface details

"""

from egregora.ingestion.base import InputSource
from egregora.ingestion.slack_input import SlackInputSource

# Phase 6: Re-export WhatsApp parser from sources/whatsapp
# Actual implementation moved to sources/whatsapp/parser.py
from egregora.sources.whatsapp.input import WhatsAppInputSource
from egregora.sources.whatsapp.parser import (
    extract_commands,
    filter_egregora_messages,
    parse_egregora_command,
    parse_multiple,
    parse_source,  # Phase 6: Renamed from parse_export (alpha - no backward compat)
)

__all__ = [
    "InputSource",
    "SlackInputSource",
    "WhatsAppInputSource",
    "extract_commands",
    "filter_egregora_messages",
    "parse_egregora_command",
    "parse_multiple",
    "parse_source",
]
