"""Ingestion stage - Compatibility layer for backward compatibility.

**DEPRECATED**: This module exists for backward compatibility only.
All functionality has been moved to `sources/` package.

**Migration Guide:**
- OLD: `from egregora.ingestion.base import InputSource`
- NEW: `from egregora.sources.base import InputSource`

- OLD: `from egregora.ingestion import parse_source`
- NEW: `from egregora.sources.whatsapp.parser import parse_source`
  OR: `from egregora.ingestion import parse_source` (re-exported for compatibility)

**Phase 2.4 Consolidation (2025-01-09)**:
The ingestion/ directory has been consolidated into sources/:
- ingestion/base.py → sources/base.py (merged with pipeline/adapters.py)
- ingestion/slack_input.py → sources/slack/adapter.py
- This __init__.py kept as compatibility layer only

**What moved where:**
```
OLD STRUCTURE:                    NEW STRUCTURE:
ingestion/                        sources/
├── base.py                  →    ├── base.py (InputSource + SourceAdapter)
├── slack_input.py           →    ├── slack/
└── __init__.py (this file)       │   ├── adapter.py
                                  │   └── __init__.py
pipeline/                         └── whatsapp/ (already existed)
└── adapters.py              →        (merged into sources/base.py)
```

**Re-exports for compatibility:**
This module re-exports commonly used parsers and utilities so existing code
continues to work without changes.
"""

# Re-export base classes from sources/base (moved from ingestion/base)
from egregora.sources.base import InputSource, input_registry

# Re-export Slack adapter from sources/slack (moved from ingestion/slack_input)
from egregora.sources.slack import SlackInputSource

# Re-export WhatsApp implementation from sources/whatsapp
from egregora.sources.whatsapp.input import WhatsAppInputSource
from egregora.sources.whatsapp.parser import (
    extract_commands,
    filter_egregora_messages,
    parse_egregora_command,
    parse_multiple,
    parse_source,  # Phase 6: Renamed from parse_export (alpha - no backward compat)
)

# Register built-in adapters (maintain existing behavior)
input_registry.register(WhatsAppInputSource)
input_registry.register(SlackInputSource)

__all__ = [
    "InputSource",
    "SlackInputSource",
    "WhatsAppInputSource",
    "extract_commands",
    "filter_egregora_messages",
    "input_registry",
    "parse_egregora_command",
    "parse_multiple",
    "parse_source",
]
