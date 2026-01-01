# Input Adapters Reference

Input adapters convert platform-specific exports (WhatsApp, IPERON, etc.) into Egregora's standardized Intermediate Representation (IR) schema.

## Overview

All input adapters implement the `InputAdapter` abstract base class, which provides a consistent interface for:

1. **Parsing raw exports** from specific platforms
2. **Converting messages** to the standardized IR schema (Ibis Table)
3. **Extracting and delivering media files** (optional)
4. **Providing export metadata** (optional)

The adapter registry automatically discovers and validates all available adapters.

## Base Adapter Interface

The abstract base class that all input adapters must implement.

::: egregora.input_adapters.base.InputAdapter
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      show_category_heading: true

## Adapter Types and Registry

### AdapterMeta

Metadata for adapter discovery and plugin loading.

::: egregora.input_adapters.base.AdapterMeta
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4
      members_order: source

### Export

Common metadata for chat exports.

::: egregora.input_adapters.base.Export
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4
      members_order: source

### MediaMapping

::: egregora.input_adapters.base.MediaMapping
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4
      members_order: source

### Adapter Registry

The registry automatically discovers and manages all available adapters.

::: egregora.input_adapters.registry
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Built-in Adapters

### WhatsApp Adapter

Parses WhatsApp chat exports (TXT format) and extracts messages, media, and participants.

::: egregora.input_adapters.whatsapp.adapter.WhatsAppInputAdapter
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false
      show_category_heading: true

#### WhatsApp Parsing Utilities

Low-level parsing functions for WhatsApp export format.

::: egregora.input_adapters.whatsapp.parsing
    options:
      show_source: false
      show_root_heading: true
      heading_level: 5
      members_order: source
      show_if_no_docstring: false

#### WhatsApp Utilities

Helper functions for WhatsApp data processing.

::: egregora.input_adapters.whatsapp.utils
    options:
      show_source: false
      show_root_heading: true
      heading_level: 5
      members_order: source
      show_if_no_docstring: false

### IPERON Adapter

Parses IPERON/TJRO institutional record exports.

::: egregora.input_adapters.iperon_tjro
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Self-Reflection Adapter

Generates synthetic reflective content based on existing posts.

::: egregora.input_adapters.self_reflection
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Usage Examples

### Using an Adapter Programmatically

```python
from pathlib import Path
from egregora.input_adapters.whatsapp import WhatsAppInputAdapter

# Initialize adapter
adapter = WhatsAppInputAdapter()

# Parse WhatsApp export
export_path = Path("./whatsapp-export")
table = adapter.parse(export_path)

# Table conforms to IR schema
print(table.schema())  # Shows IR columns: message_id, content, timestamp, etc.

# Extract media files
media_files = adapter.extract_media(export_path)
for doc in media_files:
    print(f"Media: {doc.metadata['filename']}")
```

### Using the Adapter Registry

```python
from egregora.input_adapters.registry import get_adapter_registry

# Get registry
registry = get_adapter_registry()

# List available adapters
for identifier, adapter_class in registry.items():
    meta = adapter_class.get_adapter_metadata()
    print(f"{identifier}: {meta['name']} v{meta['version']}")

# Get specific adapter
WhatsAppAdapter = registry.get_adapter("whatsapp")
adapter = WhatsAppAdapter()
```

### Via CLI

```bash
# List available source adapters
egregora show sources

# Use WhatsApp adapter
egregora write ./my-site \
  --source whatsapp \
  --source-path ./whatsapp-export

# Use IPERON adapter
egregora write ./my-site \
  --source iperon \
  --source-path ./iperon-data.json
```

## Creating Custom Adapters

To create a custom input adapter:

1. **Inherit from `InputAdapter`**:

```python
from egregora.input_adapters.base import InputAdapter, AdapterMeta
from pathlib import Path
from ibis.expr.types import Table

class MyCustomAdapter(InputAdapter):
    @property
    def source_name(self) -> str:
        return "My Platform"

    @property
    def source_identifier(self) -> str:
        return "myplatform"

    @classmethod
    def get_adapter_metadata(cls) -> AdapterMeta:
        return {
            "name": "My Platform",
            "version": "1.0.0",
            "source": "myplatform",
            "doc_url": "https://example.com/docs",
            "ir_version": "v1",
        }

    def parse(self, source_path: Path, **kwargs) -> Table:
        # Parse platform export and return IR-compliant table
        # Must include columns: message_id, content, timestamp, author, etc.
        pass
```

2. **Register the adapter**:

```python
from egregora.input_adapters.registry import get_adapter_registry

registry = get_adapter_registry()
registry.register("myplatform", MyCustomAdapter)
```

3. **Use it**:

```bash
egregora write ./my-site --source myplatform --source-path ./my-export
```

## IR Schema Requirements

All adapters must return an Ibis Table with these columns:

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `message_id` | `UUID` | Yes | Unique message identifier |
| `content` | `string` | Yes | Message text content |
| `timestamp` | `timestamp` | Yes | Message timestamp (UTC) |
| `author` | `string` | Yes | Message author identifier |
| `author_name` | `string` | No | Human-readable author name |
| `reply_to` | `UUID` | No | ID of message being replied to |
| `media_files` | `array<string>` | No | List of media file paths |
| `metadata` | `struct` | No | Platform-specific metadata |

See the IR schema documentation for full details.
