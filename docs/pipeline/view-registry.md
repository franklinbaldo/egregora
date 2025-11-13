# Pipeline View Registry (Priority C.1)

**Status**: Implemented (2025-01-09)
**Module**: `egregora.pipeline.views`

## Overview

The **View Registry** provides a centralized system for managing pipeline view builders - reusable Ibis table transformations that can be referenced by name across pipeline stages.

## Why View Registry?

**Problems it solves:**

1. **Scattered transformations**: Without a registry, similar transformations are duplicated across pipeline stages
2. **Hard to test**: Testing transformations requires importing and calling specific stage functions
3. **SQL optimization unclear**: No clear pattern for using SQL when Ibis is too slow
4. **Coupling**: Stages are tightly coupled to specific transformation implementations

**Benefits:**

1. **Centralized definitions**: All view transformations in one place
2. **Easy testing**: Swap views for mocks in tests
3. **Flexible optimization**: Transparently swap Ibis ↔ SQL implementations
4. **Loose coupling**: Stages reference views by name, not implementation

## Architecture

```python
from egregora.database.views import views, ViewRegistry

# View builders are callables: Table → Table
ViewBuilder = Callable[[Table], Table]

# Global registry (singleton)
views = ViewRegistry()

# Register views with decorator
@views.register("my_view")
def my_view_builder(ir: Table) -> Table:
    return ir.filter(ir.text.notnull())

# Use in pipeline stages
def my_stage(table: Table) -> Table:
    builder = views.get("my_view")
    return builder(table)
```

## Usage

### Registering Views

**Option 1: Decorator** (recommended)

```python
from egregora.database.views import views

@views.register("enriched_messages")
def enriched_messages(ir: Table) -> Table:
    """Filter to messages with enriched metadata."""
    return ir.filter(ir.media_description.notnull())
```

**Option 2: Direct registration**

```python
from egregora.database.views import views

def my_filter(ir: Table) -> Table:
    return ir.limit(100)

views.register_function("limited", my_filter)
```

### Using Views in Pipeline Stages

```python
from egregora.database.views import views

def chunking_stage(ir_table: Table) -> Table:
    """Chunk messages into windows."""
    # Get view builder by name
    chunks_builder = views.get("chunks")

    # Apply transformation
    return chunks_builder(ir_table)
```

### Swapping Ibis ↔ SQL for Performance

**Ibis version** (default):

```python
@views.register("chunks")
def chunks_view(ir: Table) -> Table:
    """Chunk using Ibis expressions."""
    win = ibis.window(group_by="thread_id", order_by="ts")
    return ir.mutate(chunk_idx=ibis.row_number().over(win))
```

**SQL version** (optimized):

```python
@views.register("chunks_optimized")
def chunks_sql(ir: Table) -> Table:
    """Chunk using raw SQL for performance."""
    return ir.sql("""
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY thread_id
                ORDER BY ts
            ) AS chunk_idx
        FROM ir
    """)
```

**Swap at runtime:**

```python
# Development: use Ibis
builder = views.get("chunks")

# Production: use SQL
builder = views.get("chunks_optimized")
```

## Built-in Views

The global registry includes these common views:

| View Name | Description | Type |
|-----------|-------------|------|
| `chunks` | Add chunk_idx with row numbering by thread | Ibis |
| `chunks_optimized` | Same as chunks but with SQL | SQL |
| `messages_with_media` | Filter to messages with media_url | Ibis |
| `messages_with_text` | Filter to non-empty text messages | Ibis |
| `hourly_aggregates` | Aggregate by hour with stats | Ibis |
| `daily_aggregates` | Aggregate by day with stats | Ibis |

**Usage:**

```python
from egregora.database.views import views

# Get built-in view
media_filter = views.get("messages_with_media")
result = media_filter(my_table)
```

## Custom Views for Your Project

Register custom views specific to your pipeline:

```python
from egregora.database.views import views

@views.register("high_engagement")
def high_engagement_filter(ir: Table) -> Table:
    """Filter to threads with >100 messages."""
    return (
        ir.group_by("thread_id")
        .having(ibis._.count() > 100)
        .select(ir)
    )

@views.register("recent_month")
def recent_month_filter(ir: Table) -> Table:
    """Filter to messages in the last 30 days."""
    import ibis
    cutoff = ibis.now() - ibis.interval(days=30)
    return ir.filter(ir.ts >= cutoff)
```

## Testing with View Registry

**Mock views for testing:**

```python
def test_my_stage():
    """Test pipeline stage with mocked view."""
    from egregora.database.views import ViewRegistry

    # Create test registry
    test_views = ViewRegistry()

    # Register mock view
    @test_views.register("chunks")
    def mock_chunks(ir: Table) -> Table:
        # Simplified version for testing
        return ir.mutate(chunk_idx=1)

    # Use test registry in stage
    result = my_stage(test_table, view_registry=test_views)

    assert result is not None
```

## API Reference

### `ViewRegistry`

**Class: Central registry for view builders**

```python
class ViewRegistry:
    def __init__(self) -> None:
        """Initialize empty registry."""

    def register(self, name: str) -> Callable:
        """Decorator to register a view builder.

        Args:
            name: Unique view identifier

        Raises:
            ValueError: If name already registered
        """

    def register_function(self, name: str, func: ViewBuilder) -> None:
        """Register a view builder directly."""

    def get(self, name: str) -> ViewBuilder:
        """Get view builder by name.

        Raises:
            KeyError: If view not found
        """

    def has(self, name: str) -> bool:
        """Check if view exists."""

    def list_views(self) -> list[str]:
        """List all registered view names (sorted)."""

    def unregister(self, name: str) -> None:
        """Remove a view from registry."""

    def clear(self) -> None:
        """Remove all views."""
```

### `ViewBuilder`

**Type alias for view builder functions:**

```python
ViewBuilder = Callable[[Table], Table]
```

A view builder:
- Takes an Ibis Table as input
- Returns an Ibis Table as output
- Can use Ibis expressions or raw SQL

### `views`

**Global registry singleton:**

```python
from egregora.database.views import views

# Pre-registered with common views
views.list_views()
# ['chunks', 'chunks_optimized', 'daily_aggregates', ...]
```

## Design Patterns

### Pattern 1: Layered Views

Build complex views from simpler ones:

```python
@views.register("base_messages")
def base_messages(ir: Table) -> Table:
    """Filter to valid messages."""
    return ir.filter(
        ir.text.notnull() &
        (ir.text != "")
    )

@views.register("enriched_messages")
def enriched_messages(ir: Table) -> Table:
    """Enriched messages built on base."""
    base = views.get("base_messages")(ir)
    return base.filter(base.media_description.notnull())
```

### Pattern 2: Parameterized View Builders

Return a view builder with baked-in parameters:

```python
def create_limit_view(n: int) -> ViewBuilder:
    """Factory for limit views."""
    def limiter(ir: Table) -> Table:
        return ir.limit(n)
    return limiter

# Register with different limits
views.register_function("top_10", create_limit_view(10))
views.register_function("top_100", create_limit_view(100))
```

### Pattern 3: SQL for Complex Aggregations

Use SQL when Ibis is verbose:

```python
@views.register("thread_stats_sql")
def thread_stats_sql(ir: Table) -> Table:
    """Complex stats with SQL for readability."""
    return ir.sql("""
        SELECT
            thread_id,
            COUNT(*) as msg_count,
            COUNT(DISTINCT author_uuid) as unique_authors,
            MIN(ts) as thread_start,
            MAX(ts) as thread_end,
            MAX(ts) - MIN(ts) as thread_duration,
            AVG(LENGTH(text)) as avg_msg_length
        FROM ir
        GROUP BY thread_id
        HAVING msg_count > 5
        ORDER BY msg_count DESC
    """)
```

## Comparison with Database Views

Egregora has **two view systems**:

| Feature | Pipeline Views (`pipeline/views.py`) | Database Views (`database/views.py`) |
|---------|--------------------------------------|--------------------------------------|
| **Purpose** | Pipeline transformations | Query optimization |
| **Format** | Callable functions (Ibis/SQL) | SQL strings |
| **Storage** | In-memory registry | Materialized in DuckDB |
| **Use case** | Stage composition | Performance caching |
| **Example** | `chunks` view for windowing | `author_message_counts` materialized table |

**When to use which:**

- **Pipeline views**: Stage logic, reusable transformations, testing
- **Database views**: Expensive queries, pre-computed aggregations, caching

## Migration Guide

**Before (without registry):**

```python
def chunking_stage(ir_table: Table) -> Table:
    # Transformation inline
    win = ibis.window(group_by="thread_id", order_by="ts")
    return ir_table.mutate(chunk_idx=ibis.row_number().over(win))
```

**After (with registry):**

```python
from egregora.database.views import views

def chunking_stage(ir_table: Table) -> Table:
    # Reference by name
    chunks_builder = views.get("chunks")
    return chunks_builder(ir_table)
```

**Benefits:**
- Transformation can be tested independently
- Can swap `chunks` ↔ `chunks_optimized` without changing stage
- Multiple stages can reuse the same transformation

## Performance Considerations

**Ibis vs SQL:**

- **Ibis**: Better for complex Python logic, type safety, IDE support
- **SQL**: Better for performance-critical aggregations, window functions

**Benchmark and decide:**

```python
import time

# Benchmark Ibis version
start = time.time()
result_ibis = views.get("chunks")(large_table).execute()
ibis_time = time.time() - start

# Benchmark SQL version
start = time.time()
result_sql = views.get("chunks_optimized")(large_table).execute()
sql_time = time.time() - start

print(f"Ibis: {ibis_time:.2f}s, SQL: {sql_time:.2f}s")
```

## Roadmap Items Completed

- ✅ C.1: View Registry + SQL Stage Views
  - ViewRegistry class with decorator pattern
  - ViewBuilder type alias
  - Global singleton `views`
  - Built-in common views (chunks, aggregates, filters)
  - Transparent Ibis ↔ SQL swapping
  - 29 comprehensive tests

## Related Documentation

- `src/egregora/pipeline/views.py` - Implementation
- `tests/unit/test_pipeline_views.py` - Test suite
- `docs/database/views.md` - Database materialized views (different system)
- `ARCHITECTURE_ROADMAP.md` - Priority C.1 specification

## Examples

See `tests/unit/test_pipeline_views.py` for comprehensive examples of:
- Registering views
- Using views in transformations
- Testing with mocked registries
- All built-in view behaviors
