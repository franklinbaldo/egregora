# DuckDBStorageManager (Priority C.2)

**Status**: Implemented (2025-01-09)
**Module**: `egregora.database.storage`

## Overview

The **DuckDBStorageManager** provides centralized DuckDB connection management with automatic checkpointing and integration with the ViewRegistry. It eliminates raw SQL usage and provides a consistent interface for table I/O across pipeline stages.

## Why DuckDBStorageManager?

**Problems it solves:**

1. **Scattered connections**: Pipeline stages create their own DuckDB connections
2. **Inconsistent checkpointing**: No standard way to save intermediate results
3. **Raw SQL usage**: Direct SQL queries scattered across codebase
4. **Hard to test**: Difficult to mock database operations

**Benefits:**

1. **Centralized connection management**: Single source of truth for database access
2. **Automatic checkpointing**: Persist intermediate results to disk transparently
3. **Ibis-first API**: All operations use Ibis tables (no raw SQL)
4. **Easy testing**: Context manager and in-memory mode for unit tests
5. **ViewRegistry integration**: Execute named views with automatic materialization

## Architecture

```python
from egregora.database.duckdb_manager import DuckDBStorageManager

# Initialize with file or in-memory
storage = DuckDBStorageManager(db_path=Path("pipeline.duckdb"))

# Read/write tables
table = storage.read_table("conversations")
storage.write_table(enriched, "conversations_enriched", checkpoint=True)

# Execute views from registry
from egregora.database.views import views
chunks_builder = views.get("chunks")
result = storage.execute_view("chunks_materialized", chunks_builder, "conversations")
```

## Usage

### Basic Operations

**Initialize DuckDBStorageManager:**

```python
from pathlib import Path
from egregora.database.duckdb_manager import DuckDBStorageManager

# File-based (persistent)
storage = DuckDBStorageManager(db_path=Path("pipeline.duckdb"))

# In-memory (temporary)
storage = DuckDBStorageManager()

# Custom checkpoint directory
storage = DuckDBStorageManager(
    db_path=Path("pipeline.duckdb"),
    checkpoint_dir=Path(".egregora/checkpoints")
)
```

**Context Manager (recommended):**

```python
with DuckDBStorageManager(db_path=Path("pipeline.duckdb")) as storage:
    table = storage.read_table("conversations")
    # ... operations ...
# Connection automatically closed
```

### Reading Tables

```python
# Read as Ibis table
table = storage.read_table("conversations")

# Execute to pandas DataFrame
df = table.execute()

# Check if table exists first
if storage.table_exists("conversations"):
    table = storage.read_table("conversations")
```

### Writing Tables

**Without checkpoint (in-memory only):**

```python
enriched = table.mutate(score=table.rating * 2)
storage.write_table(enriched, "conversations_enriched", checkpoint=False)
```

**With checkpoint (persisted to parquet):**

```python
# Automatic parquet checkpoint
storage.write_table(
    enriched,
    "conversations_enriched",
    checkpoint=True  # Default
)

# Checkpoint saved to: .egregora/data/conversations_enriched.parquet
# AND loaded into DuckDB table
```

**Write modes:**

```python
# Replace existing table (default)
storage.write_table(table, "mytable", mode="replace")

# Append to existing table (requires checkpoint=True)
storage.write_table(table, "mytable", mode="append", checkpoint=True)
```

### Executing Views

**With ViewRegistry integration:**

```python
from egregora.database.views import views

# Get view builder
chunks_builder = views.get("chunks")

# Execute and materialize
result = storage.execute_view(
    view_name="chunks_materialized",
    builder=chunks_builder,
    input_table="conversations",
    checkpoint=True  # Save result
)

# Use result
df = result.execute()
```

**Custom view builder:**

```python
def filter_media(ir: Table) -> Table:
    return ir.filter(ir.media_url.notnull())

result = storage.execute_view(
    "media_messages",
    filter_media,
    "conversations"
)
```

### Table Management

```python
# List all tables
tables = storage.list_tables()
print(f"Tables: {tables}")

# Check existence
if storage.table_exists("conversations"):
    print("Table exists!")

# Drop table
storage.drop_table("temp_results")

# Drop table AND checkpoint
storage.drop_table("temp_results", checkpoint_too=True)
```

## Checkpointing

**Why checkpoints?**
- **Persistence**: Survive process crashes and restarts
- **Reproducibility**: Reuse expensive computations
- **Debugging**: Inspect intermediate results
- **Portability**: Parquet files are language-agnostic

**How it works:**

```python
# 1. Write table with checkpoint=True
storage.write_table(table, "enriched", checkpoint=True)

# Behind the scenes:
# a) table.to_parquet(".egregora/data/enriched.parquet")
# b) DuckDB: CREATE TABLE enriched AS SELECT * FROM read_parquet('...')

# 2. Table persists across connections
storage1.close()

storage2 = DuckDBStorageManager(db_path=Path("pipeline.duckdb"))
table = storage2.read_table("enriched")  # Still available!
```

**Checkpoint location:**

```python
# Default: .egregora/data/<table_name>.parquet
storage = DuckDBStorageManager()  # → .egregora/data/

# Custom:
storage = DuckDBStorageManager(checkpoint_dir=Path("my_checkpoints"))
```

## Integration with Pipeline Stages

**Pattern: Dependency Injection**

```python
def enrich_stage(
    storage: DuckDBStorageManager,
    config: EgregoraConfig,
    privacy_pass: PrivacyPass
) -> None:
    """Enrichment stage with injected storage."""
    # Read input
    table = storage.read_table("conversations")

    # Transform
    enriched = enrich_media(table, config, privacy_pass=privacy_pass)

    # Write output with checkpoint
    storage.write_table(enriched, "conversations_enriched")


# Usage
with DuckDBStorageManager(db_path=Path("pipeline.duckdb")) as storage:
    enrich_stage(storage, config, privacy_pass)
```

**Pattern: View-based Stages**

```python
from egregora.database.views import views

def chunking_stage(storage: DuckDBStorageManager) -> None:
    """Chunking stage using ViewRegistry."""
    chunks_builder = views.get("chunks")
    storage.execute_view(
        "chunks",
        chunks_builder,
        "conversations",
        checkpoint=True
    )


with DuckDBStorageManager(db_path=Path("pipeline.duckdb")) as storage:
    chunking_stage(storage)
```

## Testing

**Use in-memory storage for tests:**

```python
def test_my_stage():
    """Test pipeline stage with in-memory storage."""
    from egregora.database.duckdb_manager import temp_storage

    with temp_storage() as storage:
        # Create test data
        test_table = ibis.memtable({"id": [1, 2, 3]})
        storage.write_table(test_table, "input", checkpoint=False)

        # Run stage
        my_stage(storage)

        # Verify output
        result = storage.read_table("output")
        assert result.count().execute() == 3
```

**Mock for integration tests:**

```python
from unittest.mock import Mock

def test_stage_with_mock():
    mock_storage = Mock(spec=DuckDBStorageManager)
    mock_storage.read_table.return_value = test_table

    my_stage(mock_storage)

    mock_storage.write_table.assert_called_once()
```

## API Reference

### `DuckDBStorageManager`

```python
class DuckDBStorageManager:
    def __init__(
        self,
        db_path: Path | None = None,
        checkpoint_dir: Path | None = None,
    ) -> None:
        """Initialize storage manager.

        Args:
            db_path: Path to DuckDB file (None = in-memory)
            checkpoint_dir: Checkpoint directory (default: .egregora/data)
        """

    def read_table(self, name: str) -> Table:
        """Read table as Ibis expression."""

    def write_table(
        self,
        table: Table,
        name: str,
        mode: Literal["replace", "append"] = "replace",
        checkpoint: bool = True,
    ) -> None:
        """Write Ibis table to DuckDB."""

    def execute_view(
        self,
        view_name: str,
        builder: ViewBuilder,
        input_table: str,
        checkpoint: bool = True,
    ) -> Table:
        """Execute view builder and materialize result."""

    def table_exists(self, name: str) -> bool:
        """Check if table exists."""

    def list_tables(self) -> list[str]:
        """List all tables."""

    def drop_table(self, name: str, *, checkpoint_too: bool = False) -> None:
        """Drop table from database."""

    def close(self) -> None:
        """Close database connection."""
```

### `temp_storage()`

```python
def temp_storage() -> DuckDBStorageManager:
    """Create temporary in-memory storage manager."""
```

## Design Patterns

### Pattern 1: Pipeline Stage

```python
def process_stage(
    storage: DuckDBStorageManager,
    config: Config
) -> None:
    """Generic processing stage."""
    input_table = storage.read_table("input")
    output_table = process(input_table, config)
    storage.write_table(output_table, "output")
```

### Pattern 2: Checkpoint Recovery

```python
def resumable_stage(storage: DuckDBStorageManager) -> None:
    """Stage that can resume from checkpoint."""
    if storage.table_exists("partial_results"):
        logger.info("Resuming from checkpoint")
        table = storage.read_table("partial_results")
    else:
        logger.info("Starting from scratch")
        table = load_initial_data()

    # Process...
    result = process(table)

    # Save checkpoint
    storage.write_table(result, "partial_results", checkpoint=True)
```

### Pattern 3: Multi-Table Join

```python
def join_stage(storage: DuckDBStorageManager) -> None:
    """Join multiple tables."""
    conversations = storage.read_table("conversations")
    profiles = storage.read_table("profiles")

    joined = conversations.join(
        profiles,
        conversations.author_uuid == profiles.author_uuid
    )

    storage.write_table(joined, "enriched_conversations")
```

## Comparison with Raw SQL

**Before (raw SQL):**

```python
import duckdb

conn = duckdb.connect("pipeline.duckdb")
conn.execute("CREATE TABLE enriched AS SELECT * FROM conversations WHERE ...")
df = conn.execute("SELECT * FROM enriched").fetchdf()
```

**After (DuckDBStorageManager):**

```python
with DuckDBStorageManager(db_path=Path("pipeline.duckdb")) as storage:
    table = storage.read_table("conversations")
    enriched = table.filter(...)
    storage.write_table(enriched, "enriched")
    df = enriched.execute()
```

**Benefits:**
- Type-safe Ibis API
- Automatic checkpointing
- Centralized connection management
- Easy testing and mocking

## Performance Considerations

**In-memory vs File-based:**

```python
# In-memory (fast, no persistence)
storage = DuckDBStorageManager()

# File-based (slower, persists)
storage = DuckDBStorageManager(db_path=Path("pipeline.duckdb"))
```

**Checkpoint overhead:**

```python
# No checkpoint (fastest, no persistence)
storage.write_table(table, "temp", checkpoint=False)

# With checkpoint (slower, persists to parquet)
storage.write_table(table, "important", checkpoint=True)
```

**Recommendation:**
- Use `checkpoint=False` for temporary/intermediate tables
- Use `checkpoint=True` for expensive computations and final results

## Roadmap Items Completed

- ✅ C.2: DuckDBStorageManager + No Raw SQL
  - Centralized DuckDB connection management
  - Automatic parquet checkpointing
  - Ibis-first API (no raw SQL)
  - ViewRegistry integration
  - Context manager support
  - 22 comprehensive tests

## Related Documentation

- `src/egregora/database/storage.py` - Implementation
- `tests/unit/test_storage_manager.py` - Test suite (22 tests)
- `docs/pipeline/view-registry.md` - ViewRegistry (C.1)
- `ARCHITECTURE_ROADMAP.md` - Priority C.2 specification

## Migration Guide

**Before:**

```python
import duckdb

conn = duckdb.connect("pipeline.duckdb")
conn.execute("CREATE TABLE enriched AS SELECT ...")
df = conn.execute("SELECT * FROM enriched").fetchdf()
conn.close()
```

**After:**

```python
from egregora.database import DuckDBStorageManager

with DuckDBStorageManager(db_path=Path("pipeline.duckdb")) as storage:
    table = storage.read_table("conversations")
    enriched = table.mutate(...)
    storage.write_table(enriched, "enriched")
```

**Benefits:**
- No raw SQL strings
- Type-safe operations
- Automatic resource cleanup
- Built-in checkpointing
- Easy testing

## Examples

See `tests/unit/test_storage_manager.py` for comprehensive examples of:
- Initialization patterns
- Table read/write operations
- Checkpoint persistence
- View execution
- Testing strategies
- Edge cases
