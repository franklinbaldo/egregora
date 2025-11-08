# Creating Custom Adapters

This guide explains how to create custom source adapters for Egregora, enabling support for new chat platforms (Discord, Telegram, Matrix, etc.).

## Overview

Egregora uses a **plugin architecture** for source adapters. Adapters:
- Convert platform-specific exports → standardized IR (Intermediate Representation)
- Are automatically discovered via Python entry points
- Must implement the `SourceAdapter` protocol
- Support IR v1 schema

## Quick Start

### 1. Create Adapter Class

Create a Python class that implements `SourceAdapter`:

```python
from pathlib import Path
from egregora.pipeline.adapters import SourceAdapter, AdapterMeta
import ibis

class DiscordAdapter(SourceAdapter):
    """Adapter for Discord JSON exports."""

    @property
    def source_name(self) -> str:
        return "Discord"

    @property
    def source_identifier(self) -> str:
        return "discord"

    def adapter_meta(self) -> AdapterMeta:
        """Return adapter metadata for plugin discovery."""
        return AdapterMeta(
            name="Discord",
            version="1.0.0",
            source="discord",
            doc_url="https://github.com/yourname/egregora-discord",
            ir_version="v1"
        )

    def parse(self, input_path: Path, *, timezone: str | None = None, **kwargs) -> ibis.Table:
        """Parse Discord export into IR-compliant table."""
        # Your parsing logic here
        # Must return Ibis table matching IR v1 schema
        pass
```

### 2. Register as Plugin

In your package's `pyproject.toml`:

```toml
[project.entry-points."egregora.adapters"]
discord = "egregora_discord:DiscordAdapter"
```

### 3. Install & Verify

```bash
pip install egregora-discord
egregora adapters  # Should show Discord adapter
```

---

## Adapter Protocol Reference

### Required Properties

#### `source_name` (property)
Human-readable platform name.

```python
@property
def source_name(self) -> str:
    return "Discord"
```

**Examples**: `"WhatsApp"`, `"Slack"`, `"Discord"`, `"Telegram"`

---

#### `source_identifier` (property)
Lowercase alphanumeric identifier for CLI/config.

```python
@property
def source_identifier(self) -> str:
    return "discord"
```

**Examples**: `"whatsapp"`, `"slack"`, `"discord"`, `"telegram"`

---

### Required Methods

#### `adapter_meta()` → `AdapterMeta`
Return adapter metadata for plugin discovery and validation.

```python
def adapter_meta(self) -> AdapterMeta:
    return AdapterMeta(
        name="Discord",           # Human-readable name
        version="1.0.0",          # Semantic version
        source="discord",         # Must match source_identifier
        doc_url="https://...",    # Documentation URL
        ir_version="v1"           # IR schema version (must be "v1")
    )
```

**Important**: `ir_version` must be `"v1"` or adapter will be rejected.

---

#### `parse()` → `ibis.Table`
Parse raw export into IR-compliant Ibis table.

```python
def parse(
    self,
    input_path: Path,
    *,
    timezone: str | None = None,
    **kwargs
) -> ibis.Table:
    """Parse source export into IR v1 table.

    Args:
        input_path: Path to export file (ZIP, JSON, etc.)
        timezone: Optional timezone for timestamp normalization
        **kwargs: Source-specific parameters

    Returns:
        Ibis table conforming to IR v1 schema

    Raises:
        ValueError: If input is invalid
        FileNotFoundError: If input_path missing
    """
    # Your parsing logic here
    pass
```

**IR v1 Schema** (required columns):

```python
{
    "event_id": "uuid",           # Unique message ID (UUID)
    "tenant_id": "string",        # Tenant identifier
    "source": "string",           # Source identifier ("discord")
    "thread_id": "uuid",          # Conversation/channel UUID
    "msg_id": "string",           # Original message ID
    "ts": "timestamp",            # Message timestamp (UTC)
    "author_raw": "string",       # Original author name
    "author_uuid": "uuid",        # Anonymized author UUID (use UUID5)
    "text": "string",             # Message content (markdown)
    "media_url": "string",        # Optional media URL
    "media_type": "string",       # Optional media type
    "attrs": "json",              # Optional metadata
    "pii_flags": "json",          # Optional PII detection flags
    "created_at": "timestamp",    # Record creation time
    "created_by_run": "uuid"      # Run ID that created this record
}
```

**Media References**: Use markdown format in `text` field:
- Images: `![alt text](filename.jpg)`
- Videos: `[Video](filename.mp4)`
- Files: `[Document](report.pdf)`

---

### Optional Methods

#### `deliver_media()` → `Path | None`
Deliver media file on demand (lazy extraction).

```python
def deliver_media(
    self,
    media_reference: str,
    temp_dir: Path,
    **kwargs
) -> Path | None:
    """Extract/download media file to temp directory.

    Args:
        media_reference: Filename from markdown link
        temp_dir: Where to write the file
        **kwargs: Source-specific params

    Returns:
        Path to delivered file, or None if not found
    """
    # Download or extract media file
    output_path = temp_dir / media_reference
    # ... write file ...
    return output_path
```

**When to implement**:
- Platform bundles media (WhatsApp ZIPs)
- Media accessible via API (Slack, Discord)

---

#### `extract_media()` → `dict[str, Path]`
Extract all media upfront (deprecated in favor of `deliver_media`).

```python
def extract_media(
    self,
    input_path: Path,
    output_dir: Path,
    **kwargs
) -> dict[str, Path]:
    """Extract all media files from export.

    Returns:
        Mapping of media references to extracted file paths
    """
    return {}  # Default: no media
```

---

#### `get_metadata()` → `dict[str, Any]`
Extract export metadata (channel name, date range, etc.).

```python
def get_metadata(self, input_path: Path, **kwargs) -> dict[str, Any]:
    """Extract source-specific metadata."""
    return {
        "channel_name": "general",
        "export_date": "2025-01-08",
        "message_count": 1000
    }
```

---

## Complete Example: Discord Adapter

```python
"""Discord adapter for Egregora."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid5, UUID

import ibis
from egregora.pipeline.adapters import SourceAdapter, AdapterMeta

logger = logging.getLogger(__name__)

# Discord namespace for UUID5 generation
DISCORD_NAMESPACE = UUID("8f3c5a2e-4b1d-4c7e-9f6a-2d8e3f1b9c4a")


class DiscordAdapter(SourceAdapter):
    """Source adapter for Discord JSON exports.

    Discord exports are JSON files with structure:
    {
        "messages": [
            {
                "id": "123456789",
                "timestamp": "2025-01-08T10:30:00.000Z",
                "content": "Hello world",
                "author": {"name": "User123", "id": "987654321"},
                "attachments": [...]
            }
        ]
    }
    """

    @property
    def source_name(self) -> str:
        return "Discord"

    @property
    def source_identifier(self) -> str:
        return "discord"

    def adapter_meta(self) -> AdapterMeta:
        return AdapterMeta(
            name="Discord",
            version="1.0.0",
            source="discord",
            doc_url="https://github.com/yourname/egregora-discord",
            ir_version="v1"
        )

    def parse(
        self,
        input_path: Path,
        *,
        timezone: str | None = None,
        **kwargs: Any
    ) -> ibis.Table:
        """Parse Discord JSON export into IR table."""
        if not input_path.exists():
            raise FileNotFoundError(f"Discord export not found: {input_path}")

        # Load Discord JSON
        with input_path.open() as f:
            data = json.load(f)

        messages = data.get("messages", [])

        # Convert to IR format
        ir_messages = []
        for msg in messages:
            # Parse timestamp
            ts_str = msg.get("timestamp", "")
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

            # Generate UUIDs
            author_raw = msg.get("author", {}).get("name", "Unknown")
            author_uuid = uuid5(DISCORD_NAMESPACE, author_raw)

            msg_id = msg.get("id", "")
            event_id = uuid5(DISCORD_NAMESPACE, f"msg:{msg_id}")

            # Channel/thread ID
            channel_id = kwargs.get("channel_id", "general")
            thread_id = uuid5(DISCORD_NAMESPACE, f"channel:{channel_id}")

            # Convert attachments to markdown
            text = msg.get("content", "")
            for attachment in msg.get("attachments", []):
                filename = attachment.get("filename", "")
                if filename.lower().endswith((".jpg", ".png", ".gif")):
                    text += f"\n![Image]({filename})"
                else:
                    text += f"\n[File]({filename})"

            ir_msg = {
                "event_id": event_id,
                "tenant_id": kwargs.get("tenant_id", "default"),
                "source": "discord",
                "thread_id": thread_id,
                "msg_id": msg_id,
                "ts": ts,
                "author_raw": author_raw,
                "author_uuid": author_uuid,
                "text": text,
                "media_url": None,
                "media_type": None,
                "attrs": {"discord_author_id": msg.get("author", {}).get("id")},
                "pii_flags": {},
                "created_at": datetime.now(UTC),
                "created_by_run": None  # Will be set by pipeline
            }
            ir_messages.append(ir_msg)

        # Convert to Ibis table
        import pandas as pd
        df = pd.DataFrame(ir_messages)
        return ibis.memtable(df)

    def get_metadata(self, input_path: Path, **kwargs: Any) -> dict[str, Any]:
        """Extract Discord export metadata."""
        with input_path.open() as f:
            data = json.load(f)

        return {
            "channel_name": data.get("channel", {}).get("name", "Unknown"),
            "message_count": len(data.get("messages", [])),
            "export_date": datetime.now(UTC).date().isoformat()
        }
```

---

## Packaging & Distribution

### 1. Project Structure

```
egregora-discord/
├── pyproject.toml
├── README.md
├── src/
│   └── egregora_discord/
│       ├── __init__.py
│       └── adapter.py
└── tests/
    └── test_discord_adapter.py
```

### 2. `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "egregora-discord"
version = "1.0.0"
description = "Discord adapter for Egregora"
authors = [{name = "Your Name", email = "you@example.com"}]
dependencies = [
    "egregora>=0.1.0",
    "ibis-framework>=9.0.0"
]

[project.entry-points."egregora.adapters"]
discord = "egregora_discord:DiscordAdapter"

[project.urls]
Homepage = "https://github.com/yourname/egregora-discord"
Documentation = "https://github.com/yourname/egregora-discord#readme"
```

### 3. Publish

```bash
python -m build
twine upload dist/*
```

---

## Testing Adapters

```python
# tests/test_discord_adapter.py

from pathlib import Path
import pytest
from egregora_discord import DiscordAdapter

def test_adapter_meta():
    """Test adapter metadata."""
    adapter = DiscordAdapter()
    meta = adapter.adapter_meta()

    assert meta["name"] == "Discord"
    assert meta["version"] == "1.0.0"
    assert meta["source"] == "discord"
    assert meta["ir_version"] == "v1"

def test_parse_export(tmp_path: Path):
    """Test parsing Discord export."""
    # Create test export
    export_path = tmp_path / "discord_export.json"
    export_path.write_text('''
    {
        "messages": [
            {
                "id": "123",
                "timestamp": "2025-01-08T10:00:00.000Z",
                "content": "Test message",
                "author": {"name": "TestUser", "id": "456"}
            }
        ]
    }
    ''')

    adapter = DiscordAdapter()
    table = adapter.parse(export_path)

    # Verify IR schema
    assert "event_id" in table.columns
    assert "author_uuid" in table.columns
    assert "text" in table.columns

    # Verify data
    df = table.execute()
    assert len(df) == 1
    assert df.iloc[0]["text"] == "Test message"
```

---

## IR Version Validation

Egregora validates IR versions during plugin loading:

```python
# ❌ This adapter will be REJECTED
def adapter_meta(self) -> AdapterMeta:
    return AdapterMeta(
        ...,
        ir_version="v2"  # INVALID - only "v1" supported
    )

# ✅ This adapter will be ACCEPTED
def adapter_meta(self) -> AdapterMeta:
    return AdapterMeta(
        ...,
        ir_version="v1"  # VALID
    )
```

When incompatible version detected:
```
WARNING: Adapter discord requires IR v2 (current: v1), skipping
```

---

## Best Practices

1. **Use UUID5 for deterministic IDs**:
   ```python
   from uuid import uuid5, UUID

   NAMESPACE = UUID("your-namespace-uuid")
   author_uuid = uuid5(NAMESPACE, author_name)
   event_id = uuid5(NAMESPACE, f"msg:{msg_id}")
   ```

2. **Handle timezones properly**:
   ```python
   from datetime import UTC, datetime

   # Always store as UTC
   ts = datetime.fromisoformat(ts_str).astimezone(UTC)
   ```

3. **Convert media to markdown**:
   ```python
   # Images
   text += f"![Image]({filename})"

   # Videos/files
   text += f"[Video]({filename})"
   ```

4. **Validate input paths**:
   ```python
   if not input_path.exists():
       raise FileNotFoundError(f"Export not found: {input_path}")
   ```

5. **Log errors gracefully**:
   ```python
   try:
       # Parsing logic
   except Exception as e:
       logger.exception(f"Failed to parse Discord export: {e}")
       raise
   ```

---

## Examples

See built-in adapters for reference:
- **WhatsApp**: `src/egregora/adapters/whatsapp.py` (production-ready)
- **Slack**: `src/egregora/adapters/slack.py` (stub/template)

---

## Plugin Registry Internals

How Egregora discovers your adapter:

1. **Entry Point Discovery**:
   ```python
   from importlib.metadata import entry_points

   for ep in entry_points(group="egregora.adapters"):
       adapter_cls = ep.load()
   ```

2. **Validation**:
   - Check `adapter_meta()` exists
   - Validate `ir_version == "v1"`
   - Verify `source` matches identifier

3. **Registration**:
   ```python
   meta = adapter.adapter_meta()
   registry[meta["source"]] = adapter
   ```

4. **Usage**:
   ```bash
   egregora process export.json --source discord
   ```

---

## Support

- **GitHub Issues**: https://github.com/franklinbaldo/egregora/issues
- **Discussions**: https://github.com/franklinbaldo/egregora/discussions
- **Examples**: See `docs/adapters/` for more examples
