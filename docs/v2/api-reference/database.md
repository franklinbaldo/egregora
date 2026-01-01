# Database Reference

Egregora uses DuckDB with Ibis for all data persistence, providing a unified interface for pipeline state, metadata, and content storage.

## Overview

The database layer provides:

- **DuckDB Storage Manager**: Centralized interface for reading/writing tables with automatic checkpointing
- **Elo Store**: Persistent storage for post rankings using Elo rating system
- **Run Store**: Pipeline run tracking and metadata
- **Task Store**: Task execution state and results
- **Message Repository**: Conversation message storage and querying
- **Views**: Named SQL views for common queries
- **Migrations**: Schema versioning and database upgrades

All database operations use Ibis expressions for type-safe, composable queries.

## Storage Manager

The central entry point for all database operations.

::: egregora.database.duckdb_manager.DuckDBStorageManager
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      show_category_heading: true

## Specialized Stores

### Elo Store

Manages Elo ratings for post quality evaluation.

::: egregora.database.elo_store.EloStore
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false
      show_category_heading: true

#### Elo Record

::: egregora.database.elo_record
    options:
      show_source: false
      show_root_heading: true
      heading_level: 5
      members_order: source
      show_if_no_docstring: false

### Run Store

Tracks pipeline execution runs and metadata.

::: egregora.database.run_store
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Task Store

Manages task execution state and results.

::: egregora.database.task_store
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Message Repository

Provides high-level interface for message queries.

::: egregora.database.message_repository
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Database Infrastructure

### Repository Pattern

Base repository interface and implementations.

::: egregora.database.repository
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Schemas

Database table schemas and validators.

::: egregora.database.schemas
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Views

Named SQL views for common queries.

::: egregora.database.views
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Migrations

Schema versioning and database upgrades.

::: egregora.database.migrations
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Database Initialization

Database setup and bootstrapping.

::: egregora.database.init
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Protocols

Type protocols for database interfaces.

::: egregora.database.protocols
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Utilities

Helper functions for database operations.

::: egregora.database.utils
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Usage Examples

### Basic Storage Operations

```python
from pathlib import Path
from egregora.database.duckdb_manager import DuckDBStorageManager
import ibis

# Create storage manager
storage = DuckDBStorageManager(db_path=Path("./my-site/pipeline.duckdb"))

# Read table as Ibis expression
messages = storage.read_table("messages")

# Query with Ibis
recent = messages.filter(
    messages.timestamp > ibis.literal("2025-01-01")
).order_by(messages.timestamp.desc())

# Write results back
storage.write_table(recent, "recent_messages")

# Checkpoint database (flush to disk)
storage.checkpoint()
```

### Using Named Views

```python
from egregora.database.views import COMMON_VIEWS

# Execute a predefined view
chunks_builder = COMMON_VIEWS["chunks"]
chunks = storage.execute_view(
    view_name="chunks",
    builder=chunks_builder,
    source_table="conversations"
)

# View results
print(chunks.execute())
```

### Elo Rating System

```python
from egregora.database.elo_store import EloStore
from pathlib import Path

# Create Elo store
elo_store = EloStore(db_path=Path("./my-site/pipeline.duckdb"))

# Initialize new post
elo_store.initialize_post(
    post_id="post-123",
    initial_rating=1500
)

# Record a comparison (post A won against post B)
elo_store.record_comparison(
    winner_id="post-123",
    loser_id="post-456",
    k_factor=32
)

# Get current ratings
ratings = elo_store.get_all_ratings()
for post_id, rating in ratings.items():
    print(f"{post_id}: {rating}")

# Get top posts
top_posts = elo_store.get_top_posts(limit=10)
```

### Message Repository

```python
from egregora.database.message_repository import MessageRepository
from datetime import date

# Create repository
repo = MessageRepository(storage)

# Get messages by author
alice_messages = repo.get_messages_by_author("alice")

# Get messages in date range
january_messages = repo.get_messages_by_date_range(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31)
)

# Get conversation threads
thread = repo.get_thread(message_id="msg-123")
```

### Pipeline Run Tracking

```python
from egregora.database.run_store import RunStore
from uuid import uuid4

# Create run store
run_store = RunStore(storage)

# Start new run
run_id = uuid4()
run_store.create_run(
    run_id=run_id,
    config={"source": "whatsapp", "window_size": 7},
    status="running"
)

# Update run status
run_store.update_run_status(run_id, "completed")

# Get run history
recent_runs = run_store.get_recent_runs(limit=10)
```

### Migrations

```python
from egregora.database.migrations import run_migrations

# Run all pending migrations
run_migrations(db_path=Path("./my-site/pipeline.duckdb"))

# Migrations are versioned and idempotent
# Safe to run multiple times
```

## Database Schema

### Core Tables

| Table | Description |
|-------|-------------|
| `messages` | Raw conversation messages from input adapters |
| `windows` | Conversation windows (time-based message groups) |
| `documents` | Generated documents (posts, profiles, enrichments) |
| `elo_ratings` | Post quality ratings |
| `runs` | Pipeline execution history |
| `tasks` | Task execution state |

### Schema Validation

All tables use Ibis schemas with strong typing:

```python
from egregora.database.schemas import MESSAGES_SCHEMA

# Schema includes:
# - message_id: UUID
# - content: string
# - timestamp: timestamp
# - author: string
# - metadata: struct
```

## Performance Considerations

### Checkpointing

The storage manager uses automatic checkpointing to ensure data durability:

```python
# Manual checkpoint
storage.checkpoint()

# Checkpoints are also triggered automatically:
# - After write_table()
# - On context manager exit
# - Before read operations
```

### Connection Management

Always use the context manager for raw connection access:

```python
# Correct: connection is automatically released
with storage.connection() as conn:
    result = conn.execute("SELECT COUNT(*) FROM messages").fetchone()

# Avoid: holding connection reference
conn = storage._conn  # Don't do this!
```

### Query Optimization

Use Ibis expressions for optimal query performance:

```python
# Good: Ibis pushes filter to DuckDB
recent = messages.filter(messages.timestamp > cutoff).count()

# Less efficient: materializing then filtering in Python
all_msgs = messages.execute()
recent = len([m for m in all_msgs if m.timestamp > cutoff])
```

## Thread Safety

The `DuckDBStorageManager` uses thread-local storage for connections:

- Each thread gets its own connection
- Safe for concurrent reads
- Writes are serialized via DuckDB's MVCC
- No external locking required

```python
from concurrent.futures import ThreadPoolExecutor

# Safe: each thread gets own connection
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(storage.read_table, "messages")
        for _ in range(10)
    ]
    results = [f.result() for f in futures]
```

## Error Handling

Database operations raise specific exceptions (see [Exceptions Reference](exceptions.md)):

```python
from egregora.database.exceptions import (
    TableNotFoundError,
    InvalidTableNameError,
    SequenceNotFoundError,
)

try:
    table = storage.read_table("nonexistent")
except TableNotFoundError as e:
    print(f"Table not found: {e}")

try:
    storage.write_table(data, "invalid-name!")
except InvalidTableNameError as e:
    print(f"Invalid table name: {e}")
```
