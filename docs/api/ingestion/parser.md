# Ingestion - Parser

Parse WhatsApp chat exports into structured Ibis DataFrames.

## Overview

The parser module converts WhatsApp `.zip` exports into a structured format that can be processed by the rest of the pipeline.

## API Reference

::: egregora.ingestion.parser
    options:
      show_root_heading: true
      show_source: true
      members_order: source

## Usage

### Basic Parsing

```python
from egregora.ingestion import parse_whatsapp_export

# Parse a WhatsApp export
df = parse_whatsapp_export("whatsapp-export.zip")

# Result is an Ibis DataFrame with schema:
# - timestamp: datetime
# - author: string
# - message: string
# - media_type: string (optional)
# - media_path: string (optional)
```

### Supported Formats

The parser handles multiple WhatsApp export formats:

- **iOS format**: `[1/15/25, 10:30:45 AM] John: Hello`
- **Android format**: `1/15/25, 10:30 - John: Hello`
- **International**: Various date/time formats

### Media References

WhatsApp exports may include media references:

```
[1/15/25, 10:30:45 AM] John: <attached: IMG_1234.jpg>
[1/15/25, 10:31:00 AM] Jane: <attached: VID_5678.mp4>
```

The parser extracts:

- `media_type`: `image`, `video`, `audio`, `document`
- `media_path`: Filename (file not included in export without media)

## Implementation Details

### Parsing Strategy

1. **Unzip**: Extract `_chat.txt` from `.zip`
2. **Detect format**: Identify iOS vs Android format
3. **Line-by-line parsing**: Use regex to extract components
4. **Multi-line messages**: Handle messages spanning multiple lines
5. **Media detection**: Identify media references
6. **DataFrame construction**: Convert to Ibis table

### Performance

- **Streaming**: Large files are processed in chunks
- **Lazy evaluation**: Ibis defers computation until needed
- **Memory efficient**: No need to load entire file into memory

## Examples

### Filter by Date

```python
from egregora.ingestion import parse_whatsapp_export
import ibis

df = parse_whatsapp_export("export.zip")

# Filter to specific date range
filtered = df.filter(
    (df.timestamp >= '2025-01-01') &
    (df.timestamp < '2025-02-01')
)
```

### Count Messages per Author

```python
df = parse_whatsapp_export("export.zip")

message_counts = (
    df.group_by("author")
    .aggregate(count=df.count())
    .order_by(ibis.desc("count"))
)
```

### Extract Media Messages

```python
df = parse_whatsapp_export("export.zip")

media_messages = df.filter(df.media_type.notnull())
```

## Error Handling

The parser handles common issues:

- **Invalid dates**: Skipped with warning
- **Malformed lines**: Logged and skipped
- **Empty files**: Returns empty DataFrame
- **Corrupt ZIP**: Raises `ValueError`

## See Also

- [Privacy - Anonymizer](../privacy/anonymizer.md) - Next stage in pipeline
- [Core - Schema](../core/schema.md) - DataFrame schemas
