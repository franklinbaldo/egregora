# Input/Output Abstraction Layer

## Overview

Egregora now includes a flexible abstraction layer that makes it easy to:
- **Add new input sources** beyond WhatsApp (Slack, Discord, Telegram, etc.)
- **Add new output formats** beyond MkDocs (Hugo, Jekyll, custom formats)
- **Mix and match** any input source with any output format

The abstraction layer maintains the same data pipeline while allowing flexible input and output adapters.

## Architecture

### Data Flow

```
Input Source → Ibis Table → Pipeline Stages → Output Format
   (Parse)      (Standard)    (Transform)      (Write)
```

1. **Input Source**: Parses raw data (ZIP, JSON, API) into standardized Ibis Tables
2. **Pipeline**: Transforms data (anonymization, enrichment, RAG) - remains unchanged
3. **Output Format**: Writes processed data to blog/site format

### Key Components

```
src/egregora/core/
├── input_source.py      # InputSource ABC and registry
├── output_format.py     # OutputAdapter ABC and registry
└── registry.py          # Auto-registration of implementations

src/egregora/ingestion/
├── whatsapp_input.py    # WhatsApp implementation
└── slack_input.py       # Slack template (example)

src/egregora/init/
├── mkdocs_output.py     # MkDocs implementation
└── hugo_output.py       # Hugo template (example)
```

## Using the Abstraction Layer

### Basic Usage

```python
from egregora.data_primitives import input_registry, output_registry

# List available sources and formats
print(input_registry.list_sources())    # ['whatsapp', 'slack', ...]
print(output_registry.list_formats())   # ['mkdocs', 'hugo', ...]

# Get an input source
whatsapp_source = input_registry.get_source('whatsapp')

# Parse input
table, metadata = whatsapp_source.parse(
    source_path=Path("export.zip"),
    group_name="My Group",
)

# Get an output format
mkdocs_format = output_registry.get_format('mkdocs')

# Write output
mkdocs_format.write_post(
    content="# My Post\n\nContent here...",
    metadata={
        "title": "My Post",
        "slug": "my-post",
        "date": "2025-01-15",
    },
    output_dir=Path("docs/posts"),
)
```

### Auto-Detection

The registries support auto-detection:

```python
from pathlib import Path
from egregora.data_primitives import input_registry, output_registry

# Detect input source automatically
source = input_registry.detect_source(Path("export.zip"))
if source:
    print(f"Detected: {source.source_type}")  # "whatsapp"
    table, metadata = source.parse(Path("export.zip"))

# Detect output format automatically
output_format = output_registry.detect_format(Path("my-site"))
if output_format:
    print(f"Detected: {output_format.format_type}")  # "mkdocs"
```

## Adding a New Input Source

To add support for a new messaging platform (e.g., Slack, Discord):

### Step 1: Create Input Source Class

Create a new file: `src/egregora/ingestion/<platform>_input.py`

```python
from pathlib import Path
from ibis.expr.types import Table
from egregora.core.input_source import InputSource, InputMetadata

class SlackInputSource(InputSource):
    @property
    def source_type(self) -> str:
        return "slack"

    def supports_format(self, source_path: Path) -> bool:
        """Check if path is a valid Slack export."""
        # Example: check for channels.json and users.json
        return (
            source_path.is_dir() and
            (source_path / "channels.json").exists() and
            (source_path / "users.json").exists()
        )

    def parse(
        self,
        source_path: Path,
        **kwargs
    ) -> tuple[Table, InputMetadata]:
        """Parse Slack export into standardized Ibis Table."""
        # 1. Load and parse Slack JSON files
        # 2. Convert to MESSAGE_SCHEMA format:
        #    - timestamp: datetime
        #    - date: date
        #    - author: string
        #    - message: string
        #    - original_line: string
        #    - tagged_line: string
        #    - message_id: string
        # 3. Create Ibis table
        # 4. Return (table, metadata)
        pass

    def extract_media(
        self,
        source_path: Path,
        output_dir: Path,
        **kwargs
    ) -> dict[str, str]:
        """Extract media files (images, videos, etc.)."""
        # Download files from Slack API or extract from export
        # Return mapping: original_filename -> local_path
        pass
```

### Step 2: Register the Input Source

Add to `src/egregora/core/registry.py`:

```python
from ..ingestion.slack_input import SlackInputSource

def register_all():
    input_registry.register(WhatsAppInputSource)
    input_registry.register(SlackInputSource)  # ← Add this
    # ...
```

### Step 3: Test Your Implementation

```python
from pathlib import Path
from egregora.data_primitives import input_registry

# Get your source
slack = input_registry.get_source('slack')

# Test parsing
table, metadata = slack.parse(Path("slack-export/"))
print(f"Parsed {table.count().execute()} messages")
print(f"Group: {metadata.group_name}")
```

### Required Message Schema

All input sources must output tables conforming to `MESSAGE_SCHEMA`:

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | `datetime` | Message timestamp (timezone-aware if possible) |
| `date` | `date` | Local date |
| `author` | `string` | Author name/ID (anonymized later) |
| `message` | `string` | Message content (plain text or markdown) |
| `original_line` | `string` | Raw input line (for debugging) |
| `tagged_line` | `string` | Processed line (can be same as message) |
| `message_id` | `string` | Unique, deterministic message ID |

## Adding a New Output Format

To add support for a new static site generator (e.g., Hugo, Jekyll):

### Step 1: Create Output Format Class

Create a new file: `src/egregora/init/<format>_output.py`

```python
from pathlib import Path
from typing import Any
from egregora.core.output_format import OutputAdapter

class HugoOutputAdapter(OutputAdapter):
    @property
    def format_type(self) -> str:
        return "hugo"

    def supports_site(self, site_root: Path) -> bool:
        """Check if path is a valid Hugo site."""
        return (site_root / "config.toml").exists()

    def scaffold_site(
        self,
        site_root: Path,
        site_name: str,
        **kwargs
    ) -> tuple[Path, bool]:
        """Create Hugo site structure."""
        # 1. Create directories (content/, static/, themes/, etc.)
        # 2. Generate config.toml
        # 3. Create initial pages
        # 4. Return (config_path, was_created)
        pass

    def resolve_paths(self, site_root: Path) -> dict[str, Path]:
        """Resolve all paths for existing Hugo site."""
        # Return a mapping with:
        # - site_root, docs_dir, posts_dir, profiles_dir, media_dir
        return {
            "site_root": site_root,
            "docs_dir": site_root / "docs",
            "posts_dir": site_root / "posts",
            "profiles_dir": site_root / "profiles",
            "media_dir": site_root / "media",
        }

    def write_post(
        self,
        content: str,
        metadata: dict[str, Any],
        output_dir: Path,
        **kwargs,
    ) -> str:
        """Write post in Hugo format (TOML front matter)."""
        # 1. Build TOML front matter from metadata
        # 2. Combine with content
        # 3. Write to file (YYYY-MM-DD-slug.md)
        # 4. Return file path
        pass

    def write_profile(
        self,
        author_id: str,
        profile_data: dict[str, Any],
        profiles_dir: Path,
        **kwargs,
    ) -> str:
        """Write author profile page."""
        pass

    def load_config(self, site_root: Path) -> dict[str, Any]:
        """Load config.toml as dictionary."""
        pass

    def get_markdown_extensions(self) -> list[str]:
        """List supported markdown extensions."""
        return ["tables", "fenced_code", "footnotes", ...]
```

### Step 2: Register the Output Format

Add to `src/egregora/core/registry.py`:

```python
from ..init.hugo_output import HugoOutputAdapter

def register_all():
    # ...
    output_registry.register(MkDocsOutputAdapter)
    output_registry.register(HugoOutputAdapter)  # ← Add this
```

### Step 3: Test Your Implementation

```python
from pathlib import Path
from egregora.data_primitives import output_registry

# Get your format
hugo = output_registry.get_format('hugo')

# Test scaffolding
config, created = hugo.scaffold_site(
    site_root=Path("my-hugo-blog"),
    site_name="My Blog"
)

# Test writing
hugo.write_post(
    content="# Hello\n\nFirst post!",
    metadata={
        "title": "First Post",
        "slug": "first-post",
        "date": "2025-01-15",
    },
    output_dir=Path("my-hugo-blog/content/posts"),
)
```

## Complete Example: Custom Pipeline

Here's a complete example using the abstraction layer:

```python
from pathlib import Path
from egregora.data_primitives import input_registry, output_registry

# Parse input from any source
source = input_registry.get_source('whatsapp')
table, metadata = source.parse(
    source_path=Path("whatsapp-export.zip"),
    group_name="My Team Chat",
)

print(f"Parsed {table.count().execute()} messages")
print(f"Date range: {metadata.export_date}")

# Extract media
media_mapping = source.extract_media(
    source_path=Path("whatsapp-export.zip"),
    output_dir=Path("my-site/docs"),
    group_slug=metadata.group_slug,
    table=table,
)

print(f"Extracted {len(media_mapping)} media files")

# Process through pipeline (existing code)
from egregora.privacy.anonymizer import anonymize_table
table = anonymize_table(table)

# Write to any output format
output = output_registry.get_format('mkdocs')

# Scaffold site if needed
config_path, created = output.scaffold_site(
    site_root=Path("my-site"),
    site_name="My Team Archive",
)

if created:
    print("Created new MkDocs site")

# Resolve paths
site_config = output.resolve_paths(Path("my-site"))

# Write a post
post_path = output.write_post(
    content="# Week 1 Highlights\n\nGreat discussions this week!",
    metadata={
        "title": "Week 1 Highlights",
        "slug": "week-1-highlights",
        "date": "2025-01-15",
        "tags": ["weekly", "highlights"],
    },
    output_dir=site_config.posts_dir,
)

print(f"Wrote post to {post_path}")
```

## Templates and Examples

The codebase includes template implementations to help you get started:

- **Slack Input Source**: `src/egregora/ingestion/slack_input.py`
  - Shows how to parse JSON exports
  - Demonstrates user mapping and channel handling
  - Includes media download placeholders

- **Hugo Output Format**: `src/egregora/init/hugo_output.py`
  - Shows TOML front matter generation
  - Demonstrates directory structure creation
  - Includes config file generation

These templates are functional starting points that you can customize for your needs.

## Testing Your Implementation

### Unit Tests

Create tests for your implementations in `tests/`:

```python
# tests/test_slack_input.py
from pathlib import Path
from egregora.ingestion.slack_input import SlackInputSource

def test_slack_supports_format():
    source = SlackInputSource()
    assert source.supports_format(Path("slack-export"))
    assert not source.supports_format(Path("random-dir"))

def test_slack_parse():
    source = SlackInputSource()
    table, metadata = source.parse(Path("tests/fixtures/slack-export"))

    assert table.count().execute() > 0
    assert metadata.source_type == "slack"
    assert "timestamp" in table.columns
```

### Integration Tests

Test the full pipeline:

```python
def test_whatsapp_to_hugo():
    # Parse WhatsApp
    source = input_registry.get_source('whatsapp')
    table, _ = source.parse(Path("test.zip"))

    # Write to Hugo
    output = output_registry.get_format('hugo')
    output.scaffold_site(Path("test-site"), "Test")

    path = output.write_post(
        content="Test",
        metadata={"title": "Test", "slug": "test", "date": "2025-01-15"},
        output_dir=Path("test-site/content/posts"),
    )

    assert Path(path).exists()
```

## Migration Guide

If you have existing code using the old parser/writer functions, migration is straightforward:

### Before

```python
from egregora.ingestion.parser import parse_export
from egregora.orchestration.write_post import write_post
from egregora.core.models import WhatsAppExport

# Old way
export = WhatsAppExport(
    zip_path=Path("export.zip"),
    group_name="My Group",
    group_slug="my-group",
    export_date=date.today(),
    chat_file="_chat.txt",
    media_files=[],
)
table = parse_export(export)

# Write
write_post(content, metadata, output_dir)
```

### After

```python
from egregora.data_primitives import input_registry, output_registry

# New way - with auto-detection
source = input_registry.detect_source(Path("export.zip"))
table, metadata = source.parse(Path("export.zip"), group_name="My Group")

# Write
output = output_registry.detect_format(Path("my-site"))
output.write_post(content, metadata, output_dir)
```

The old functions still work and are used internally by the abstraction layer, so existing code continues to function.

## Best Practices

### Input Sources

1. **Validation**: Always validate input format in `supports_format()`
2. **Error Handling**: Raise descriptive errors for invalid inputs
3. **Deterministic IDs**: Generate consistent `message_id` values
4. **Timezone Handling**: Use timezone-aware datetimes when possible
5. **Media Handling**: Download/extract media files properly

### Output Formats

1. **Path Safety**: Use `safe_path_join()` to prevent path traversal
2. **Metadata Validation**: Check required fields before writing
3. **Idempotency**: Handle duplicate slugs gracefully
4. **Privacy**: Validate content doesn't contain PII
5. **Format Compliance**: Follow the output format's conventions

### Registry

1. **Auto-Registration**: Register in `registry.py` for automatic availability
2. **Naming**: Use lowercase identifiers (e.g., "whatsapp", "mkdocs")
3. **Detection**: Implement `supports_format()`/`supports_site()` carefully

## Troubleshooting

### Input Source Not Detected

```python
from egregora.data_primitives import input_registry

# Check if registered
print(input_registry.list_sources())

# Test detection manually
source = input_registry.get_source('whatsapp')
print(source.supports_format(Path("my-export.zip")))
```

### Output Format Not Detected

```python
from egregora.data_primitives import output_registry

# Check if registered
print(output_registry.list_formats())

# Test detection manually
output = output_registry.get_format('mkdocs')
print(output.supports_site(Path("my-site")))
```

### Import Errors

Make sure the registry is imported in your code:

```python
from egregora.data_primitives import input_registry, output_registry
# This triggers auto-registration
```

## Future Enhancements

Potential future improvements to the abstraction layer:

- **Streaming Support**: Handle large inputs incrementally
- **Async Operations**: Support async parsing and writing
- **Plugin System**: Load implementations from external packages
- **Config Validation**: JSON Schema validation for metadata
- **Format Conversion**: Convert between output formats
- **Multi-Source**: Combine multiple input sources
- **Incremental Processing**: Update only changed content

## See Also

- [Architecture Guide](architecture.md) - Overall system design
- [API Reference](../reference/api.md) - Detailed API documentation
- [WhatsApp Parser](../reference/parser.md) - WhatsApp implementation details
- [MkDocs Integration](../reference/mkdocs.md) - MkDocs format details
