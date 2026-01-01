# Transformations Reference

Message transformations convert raw conversation data into structured windows and enriched context for content generation.

## Overview

The transformations layer provides:

- **Windowing**: Group messages into time-based or count-based windows for processing
- **Enrichment**: Add contextual information (URL descriptions, media captions)
- **Checkpoint Management**: Resume processing from last successful window
- **Window Splitting**: Divide oversized windows to fit context limits

All transformations operate on Ibis tables for type safety and performance.

## Windowing

### Window Creation

Functions for creating conversation windows from messages.

::: egregora.transformations.windowing
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Enrichment

### Message Enrichment

Add contextual information to messages using AI agents.

::: egregora.transformations.enrichment
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Usage Examples

### Creating Time-Based Windows

```python
from egregora.transformations.windowing import create_windows
import ibis

# Create daily windows
windows = create_windows(
    messages=message_table,
    window_size=1,
    window_unit="days",
    overlap_ratio=0.0,  # No overlap
)

# Iterate windows
for window in windows:
    print(f"Window: {window['label']}")
    print(f"Messages: {window['messages'].count().execute()}")
    print(f"Time range: {window['start_time']} - {window['end_time']}")
```

### Creating Message-Count Windows

```python
# Create windows of 100 messages each
windows = create_windows(
    messages=message_table,
    window_size=100,
    window_unit="messages",
    overlap_ratio=0.2,  # 20% overlap between windows
)

# Window structure
# Window 1: messages 0-100
# Window 2: messages 80-180 (20% overlap)
# Window 3: messages 160-260
```

### Creating Byte-Sized Windows

```python
# Create windows that fit within token limits
# Useful for LLM context windows
windows = create_windows(
    messages=message_table,
    window_size=100_000,  # ~100K characters
    window_unit="bytes",
    overlap_ratio=0.1,
)

# Each window will be approximately 100K characters
# Helps prevent context overflow in LLM calls
```

### Using Checkpoints

```python
from egregora.transformations.windowing import (
    load_checkpoint,
    save_checkpoint,
    create_windows,
)
from pathlib import Path

# Load previous checkpoint
checkpoint_path = Path("./my-blog/.egregora/checkpoint.json")
checkpoint = load_checkpoint(checkpoint_path)

# Create windows, resuming from checkpoint
windows = create_windows(
    messages=message_table,
    window_size=7,
    window_unit="days",
    resume_from=checkpoint.get("last_timestamp") if checkpoint else None,
)

# Process windows
for window in windows:
    # ... process window ...

    # Save checkpoint after each window
    save_checkpoint(
        checkpoint_path=checkpoint_path,
        last_timestamp=window["end_time"],
        metadata={
            "last_window": window["label"],
            "processed_at": datetime.now().isoformat(),
        }
    )
```

### Window Splitting

```python
from egregora.transformations import split_window_into_n_parts

# Window is too large for context limit
large_window = {
    "label": "2025-01-15",
    "messages": message_table,
    "start_time": start,
    "end_time": end,
}

# Split into 3 smaller windows
split_windows = split_window_into_n_parts(
    window=large_window,
    n_parts=3,
)

# Result: 3 windows with equal message counts
# Window 1: 2025-01-15-part-1
# Window 2: 2025-01-15-part-2
# Window 3: 2025-01-15-part-3
```

### Message Enrichment

```python
from egregora.transformations.enrichment import (
    enrich_urls_in_messages,
    enrich_media_in_messages,
)

# Enrich URLs with descriptions
enriched_messages = await enrich_urls_in_messages(
    messages=message_table,
    config=egregora_config,
    max_urls=5,  # Limit enrichments per window
)

# Enrich media files with captions
enriched_media = await enrich_media_in_messages(
    messages=message_table,
    media_mapping=media_files,
    config=egregora_config,
)

# Enrichments are added as separate documents
# linked to original messages via parent_id
```

## Windowing Strategies

### Time-Based Windowing

Best for chat conversations with regular activity:

```python
# Daily windows (good for active group chats)
windows = create_windows(
    messages=messages,
    window_size=1,
    window_unit="days",
)

# Weekly windows (good for slower conversations)
windows = create_windows(
    messages=messages,
    window_size=7,
    window_unit="days",
)

# Hourly windows (good for real-time feeds)
windows = create_windows(
    messages=messages,
    window_size=6,
    window_unit="hours",
)
```

### Message-Count Windowing

Best for conversations with irregular activity:

```python
# Fixed number of messages per window
windows = create_windows(
    messages=messages,
    window_size=50,  # 50 messages per window
    window_unit="messages",
)

# Ensures consistent content volume
# regardless of time distribution
```

### Byte-Based Windowing

Best for ensuring windows fit context limits:

```python
# Windows sized by character count
windows = create_windows(
    messages=messages,
    window_size=100_000,  # ~100K characters
    window_unit="bytes",
)

# Prevents context overflow
# Good for very large conversations
```

### Overlapping Windows

Create context continuity between windows:

```python
# 20% overlap between windows
windows = create_windows(
    messages=messages,
    window_size=7,
    window_unit="days",
    overlap_ratio=0.2,  # Last 20% of window N included in window N+1
)

# Benefits:
# - Preserves conversation flow across boundaries
# - Helps LLM understand context transitions
# - Useful for narrative coherence
```

## Window Structure

Each window is a dictionary with this structure:

```python
window = {
    # Identifier
    "label": "2025-01-15",          # Window label (date or index)

    # Data
    "messages": ibis.Table,         # Ibis table of messages

    # Metadata
    "start_time": datetime,         # Window start timestamp
    "end_time": datetime,           # Window end timestamp
    "message_count": int,           # Number of messages
    "byte_size": int,               # Total size in characters

    # Optional
    "part": int,                    # Part number (if split)
    "total_parts": int,             # Total parts (if split)
}
```

## Checkpoint Format

Checkpoints are stored as JSON:

```json
{
  "last_timestamp": "2025-01-15T23:59:59+00:00",
  "last_window": "2025-01-15",
  "processed_at": "2025-01-16T10:30:00+00:00",
  "metadata": {
    "total_windows": 42,
    "total_messages": 1337,
    "source": "whatsapp"
  }
}
```

## Performance Considerations

### Window Size Selection

Choose window sizes based on your use case:

```python
# Active group chat (100+ messages/day)
window_size = 1  # day
window_unit = "days"

# Slow conversation (10-20 messages/week)
window_size = 7  # days
window_unit = "days"

# Very active chat (1000+ messages/day)
window_size = 100  # messages
window_unit = "messages"

# Large context models (Gemini 2.0+)
window_size = 500_000  # ~500K characters
window_unit = "bytes"
```

### Overlap Optimization

Overlapping windows increases processing but improves quality:

```python
# No overlap (fastest, may lose context)
overlap_ratio = 0.0

# Small overlap (good balance)
overlap_ratio = 0.1  # 10%

# Large overlap (highest quality, slower)
overlap_ratio = 0.3  # 30%
```

### Memory Efficiency

Windows use lazy evaluation via Ibis:

```python
# Messages not loaded into memory until needed
windows = create_windows(messages, ...)

# Only executed when needed
for window in windows:
    # Fetch window data on demand
    window_data = window["messages"].execute()
```

## Error Handling

Transformation operations raise specific exceptions:

```python
from egregora.transformations.exceptions import (
    InvalidSplitError,
    InvalidStepUnitError,
)

try:
    windows = create_windows(
        messages=messages,
        window_size=-1,  # Invalid
        window_unit="days",
    )
except ValueError as e:
    print(f"Invalid window size: {e}")

try:
    split = split_window_into_n_parts(window, n_parts=0)
except InvalidSplitError as e:
    print(f"Invalid split: {e}")

try:
    windows = create_windows(
        messages=messages,
        window_size=1,
        window_unit="invalid",  # Invalid unit
    )
except InvalidStepUnitError as e:
    print(f"Invalid unit: {e}")
```

## Integration with Pipeline

Transformations integrate with the pipeline orchestration:

```python
from egregora.transformations.windowing import create_windows
from egregora.transformations.enrichment import enrich_urls_in_messages
from egregora.orchestration.runner import PipelineRunner

# 1. Create windows
windows = create_windows(
    messages=message_table,
    window_size=7,
    window_unit="days",
)

# 2. Enrich messages
enriched = await enrich_urls_in_messages(
    messages=message_table,
    config=config,
)

# 3. Process with pipeline
runner = PipelineRunner(context)
results = runner.process_windows(windows)
```

## Configuration

Windowing behavior is configured via TOML:

```toml
[pipeline.windowing]
window_size = 7
window_unit = "days"
overlap_ratio = 0.1

[pipeline.enrichment]
enabled = true
max_urls_per_window = 5
```

See [Configuration Reference](../getting-started/configuration.md) for full details.
