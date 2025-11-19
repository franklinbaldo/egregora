# Pipeline Views (Updated)

**Status:** Simplified (2025-01-09)

The decorator-based view registry has been removed. Common view builders are
plain callables exported from ``egregora.database.views`` and collected in the
``COMMON_VIEWS`` mapping. Callers can import the specific transformation they
need or look it up by name without going through an indirection layer.

## Available views

- ``chunks`` / ``chunks_optimized`` – add ``chunk_idx`` to conversations
- ``messages_with_media`` – filter rows with non-null ``media_url``
- ``messages_with_text`` – filter rows with non-empty ``text``
- ``hourly_aggregates`` – hourly rollups for message counts and authors
- ``daily_aggregates`` – daily rollups for message counts and authors

## Usage

```python
from egregora.database.views import COMMON_VIEWS, messages_with_media_view

# Direct import of the callable
filtered = messages_with_media_view(table)

# Or dynamic lookup by name
builder = COMMON_VIEWS["chunks"]
chunked = builder(table)
```

When materializing results to DuckDB, pass the builder directly to
``DuckDBStorageManager.execute_view`` and let it handle checkpointing.
