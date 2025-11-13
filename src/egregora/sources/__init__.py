"""Platform-specific source implementations for chat export parsers.

**Purpose:**
This package contains concrete implementations of the `InputSource` interface
for various chat platforms (WhatsApp, Slack, Discord, etc.). Each source is
responsible for:

1. Parsing platform-specific export formats
2. Extracting media files (images, videos, audio)
3. Converting raw data into standardized Ibis Tables (MESSAGE_SCHEMA)
4. Providing metadata about the export (group name, export date, timezone)

**Organization:**
Each platform has its own subdirectory under `sources/`:

    sources/
    ├── whatsapp/          # WhatsApp export parser
    │   ├── __init__.py    # Re-exports WhatsAppInputSource
    │   ├── input.py       # WhatsAppInputSource class
    │   ├── parser.py      # Core parsing logic
    │   ├── grammar.py     # Regex patterns and parsing rules
    │   ├── models.py      # Pydantic models for messages
    │   └── pipeline.py    # Transformation pipeline
    ├── slack/             # (Future) Slack export parser
    ├── discord/           # (Future) Discord export parser
    └── base.py            # Shared utilities (Export dataclass)

**How Sources Implement InputSource:**
Each source must implement the `InputSource` abstract base class from
`sources/base.py`. This ensures consistent behavior across all parsers:

    from egregora.sources.base import InputSource, InputMetadata
    from pathlib import Path
    from ibis.expr.types import Table

    class MyPlatformInputSource(InputSource):
        @property
        def source_type(self) -> str:
            return "myplatform"  # Unique identifier

        def parse(self, source_path: Path, **kwargs) -> tuple[Table, InputMetadata]:
            # 1. Validate input format
            # 2. Parse messages into standardized format
            # 3. Return (messages_table, metadata)
            ...

        def extract_media(self, source_path: Path, output_dir: Path, **kwargs) -> dict[str, str]:
            # Extract images, videos, audio from export
            ...

        def supports_format(self, source_path: Path) -> bool:
            # Check if this parser can handle the given path
            # Example: return source_path.suffix == ".zip" and has_manifest_file()
            ...

**Example: Adding a New Source**

To add support for a new chat platform:

1. Create a new subdirectory:

    mkdir -p sources/discord

2. Implement the InputSource interface:

    # sources/discord/input.py
    from egregora.sources.base import InputSource, InputMetadata
    from pathlib import Path
    import ibis

    class DiscordInputSource(InputSource):
        @property
        def source_type(self) -> str:
            return "discord"

        def parse(self, source_path: Path, **kwargs) -> tuple[Table, InputMetadata]:
            # Parse Discord JSON export
            messages = self._parse_json(source_path)

            # Convert to Ibis table conforming to MESSAGE_SCHEMA
            table = ibis.memtable(messages)

            metadata = InputMetadata(
                source_type="discord",
                group_name=self._extract_guild_name(source_path),
                group_slug=self._slugify(guild_name),
                export_date=date.today(),
            )

            return table, metadata

        def extract_media(self, source_path: Path, output_dir: Path, **kwargs) -> dict[str, str]:
            # Extract attachments from Discord export
            ...

        def supports_format(self, source_path: Path) -> bool:
            # Check for Discord export structure
            return (source_path / "messages").exists()

3. Register the source:

    # sources/discord/__init__.py
    from egregora.sources.discord.input import DiscordInputSource

    __all__ = ["DiscordInputSource"]

4. Re-export from main ingestion package (optional, for convenience):

    # ingestion/__init__.py
    from egregora.sources.discord.input import DiscordInputSource

5. Register with the registry (in your application code):

    from egregora.sources.base import input_registry
    from egregora.sources.discord import DiscordInputSource

    input_registry.register(DiscordInputSource)

    # Now auto-detection works:
    source = input_registry.detect_source(Path("discord_export/"))
    if source:
        messages, meta = source.parse(Path("discord_export/"))

**Current Implementations:**
- `whatsapp/` - WhatsApp text export parser (Phase 6 refactoring complete)
- (Future) `slack/` - Slack export parser (currently in ingestion/slack_input.py)

See Also:
    - `sources/base.py` - InputSource interface definition
    - `database/schema.py` - MESSAGE_SCHEMA that all sources must conform to
    - `sources/whatsapp/` - Reference implementation

"""

from egregora.sources.base import Export

__all__ = ["Export"]
