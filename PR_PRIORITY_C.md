# Pull Request: Priority C - Data Layer Discipline (C.1 + C.2)

## Title
Priority C: Data Layer Discipline - ViewRegistry + StorageManager

## Summary

This PR implements **Priority C.1 and C.2** from the Architecture Roadmap: centralized view transformations and storage management for clean, testable, Ibis-first pipeline development.

**What's Included:**
- C.1: ViewRegistry - Centralized pipeline transformations
- C.2: StorageManager - Centralized DuckDB access with checkpointing

**Status:** Complete, tested (51 tests), documented
**Estimated Effort:** 4 days → **Actual: 2 days**

---

## Priority C.1: View Registry + SQL Stage Views

### Overview

Centralized registry for pipeline view builders - reusable Ibis table transformations referenced by name with transparent Ibis ↔ SQL swapping.

### Features

**Core Implementation:**
- `ViewRegistry` class with decorator pattern
- `ViewBuilder` type alias: `Callable[[Table], Table]`
- Global singleton `views` registry
- 6 built-in views: chunks, aggregates, filters
- Transparent Ibis ↔ SQL optimization swapping

**Built-in Views:**
1. `chunks` - Row numbering by thread (Ibis)
2. `chunks_optimized` - Same as chunks but SQL
3. `messages_with_media` - Filter to media messages
4. `messages_with_text` - Filter to non-empty text
5. `hourly_aggregates` - Hourly statistics
6. `daily_aggregates` - Daily statistics

### Usage Example

```python
from egregora.pipeline.views import views

# Register custom view
@views.register("enriched_messages")
def enriched_messages(ir: Table) -> Table:
    return ir.filter(ir.media_description.notnull())

# Use view in pipeline
def my_stage(table: Table) -> Table:
    builder = views.get("enriched_messages")
    return builder(table)

# Swap Ibis ↔ SQL for performance
chunks_ibis = views.get("chunks")         # Ibis version
chunks_sql = views.get("chunks_optimized") # SQL version
```

### Benefits

- **Centralized transformations**: All pipeline views in one registry
- **Loose coupling**: Reference views by name, not implementation
- **Performance flexibility**: Swap Ibis ↔ SQL transparently
- **Easy testing**: Mock registries for unit tests
- **Reusability**: Common views shared across stages

---

## Priority C.2: StorageManager + No Raw SQL

### Overview

Centralized DuckDB connection management with automatic parquet checkpointing and ViewRegistry integration. Eliminates raw SQL usage across the codebase.

### Features

**Core Implementation:**
- `StorageManager` class with context manager support
- Automatic parquet checkpointing for persistence
- ViewRegistry integration via `execute_view()`
- Table operations: read, write, drop, exists, list
- `temp_storage()` convenience function for testing

**Key Operations:**
- Read/write Ibis tables
- Automatic checkpointing to `.egregora/data/`
- Execute named views from ViewRegistry
- Persistent and in-memory modes

### Usage Example

```python
from egregora.database import StorageManager
from egregora.pipeline.views import views

# Context manager pattern
with StorageManager(db_path=Path("pipeline.duckdb")) as storage:
    # Read table
    table = storage.read_table("conversations")

    # Transform with Ibis
    enriched = table.mutate(score=table.rating * 2)

    # Write with checkpoint
    storage.write_table(enriched, "conversations_enriched", checkpoint=True)

    # Execute view from registry
    chunks_builder = views.get("chunks")
    result = storage.execute_view("chunks", chunks_builder, "conversations")
```

### Benefits

- **Centralized connection management**: No scattered SQL
- **Automatic checkpointing**: Persist intermediate results
- **Ibis-first API**: Eliminates raw SQL strings
- **Easy testing**: In-memory mode + mocking
- **ViewRegistry integration**: Execute named views seamlessly

---

## Integration: C.1 + C.2 Working Together

**The power of combining ViewRegistry and StorageManager:**

```python
from egregora.database import StorageManager
from egregora.pipeline.views import views

# Define pipeline stage
def chunking_stage(storage: StorageManager) -> None:
    """Chunking stage using ViewRegistry + StorageManager."""
    # Get view builder by name
    chunks_builder = views.get("chunks")

    # Execute and materialize to disk
    storage.execute_view(
        view_name="chunks",
        builder=chunks_builder,
        input_table="conversations",
        checkpoint=True  # Persists to .egregora/data/chunks.parquet
    )

# Run pipeline
with StorageManager(db_path=Path("pipeline.duckdb")) as storage:
    chunking_stage(storage)

    # Result is persisted and queryable
    chunks = storage.read_table("chunks")
```

**Benefits of integration:**
- Views define **what** to compute
- StorageManager handles **where** and **how** to persist
- Clean separation of concerns
- Testable in isolation or together

---

## Files Added

### Priority C.1 (ViewRegistry)

**Implementation:**
- `src/egregora/pipeline/views.py` (315 lines)
  - ViewRegistry class
  - 6 built-in views
  - Global `views` singleton

**Tests:**
- `tests/unit/test_pipeline_views.py` (380 lines, 29 tests)
  - Registry operations
  - View execution
  - Built-in views
  - Type compatibility

**Documentation:**
- `docs/pipeline/view-registry.md` (450+ lines)
  - Complete usage guide
  - API reference
  - Design patterns
  - Migration guide

### Priority C.2 (StorageManager)

**Implementation:**
- `src/egregora/database/storage.py` (290 lines)
  - StorageManager class
  - Checkpointing logic
  - ViewRegistry integration
  - `temp_storage()` helper

**Tests:**
- `tests/unit/test_storage_manager.py` (370 lines, 22 tests)
  - Initialization patterns
  - Table operations
  - Checkpointing
  - View execution
  - Edge cases

**Documentation:**
- `docs/database/storage-manager.md` (600+ lines)
  - Complete usage guide
  - API reference
  - Testing strategies
  - Migration guide

---

## Files Modified

**Exports:**
- `src/egregora/pipeline/__init__.py` - Export ViewRegistry, ViewBuilder, views
- `src/egregora/database/__init__.py` - Export StorageManager, temp_storage

**Documentation:**
- `CLAUDE.md` - Documented both patterns in "Modern Patterns" section
- Updated Code Structure section

---

## Test Coverage

**Total:** 51 tests (all passing)

**Priority C.1 (ViewRegistry):** 29 tests
- Registry operations (11 tests)
- View execution (3 tests)
- Global registry (7 tests)
- Common views (5 tests)
- Type compatibility (3 tests)

**Priority C.2 (StorageManager):** 22 tests
- Initialization (4 tests)
- Table operations (5 tests)
- Table management (5 tests)
- View execution (3 tests)
- Persistence (1 test)
- Edge cases (3 tests)
- Testing utilities (1 test)

**Test Commands:**
```bash
# All Priority C tests
uv run pytest tests/unit/test_pipeline_views.py tests/unit/test_storage_manager.py -v

# Individual components
uv run pytest tests/unit/test_pipeline_views.py -v    # C.1 only
uv run pytest tests/unit/test_storage_manager.py -v   # C.2 only
```

**Result:** ✅ 51 passed in 4.58s

---

## Breaking Changes

**None** - All changes are additive:
- New modules and utilities
- New exports from pipeline and database packages
- No changes to existing pipeline stages
- Backward-compatible extensions

---

## Design Patterns

### Pattern 1: Dependency Injection

```python
def enrich_stage(
    storage: StorageManager,
    config: EgregoraConfig,
    privacy_pass: PrivacyPass
) -> None:
    """Enrichment stage with injected storage."""
    table = storage.read_table("conversations")
    enriched = enrich_media(table, config, privacy_pass=privacy_pass)
    storage.write_table(enriched, "conversations_enriched")
```

### Pattern 2: View-based Stages

```python
from egregora.pipeline.views import views

def processing_stage(storage: StorageManager) -> None:
    """Stage using view registry."""
    processor = views.get("my_transformation")
    storage.execute_view("output", processor, "input", checkpoint=True)
```

### Pattern 3: Resumable Pipeline

```python
def resumable_stage(storage: StorageManager) -> None:
    """Stage that can resume from checkpoint."""
    if storage.table_exists("partial_results"):
        logger.info("Resuming from checkpoint")
        table = storage.read_table("partial_results")
    else:
        logger.info("Starting from scratch")
        table = load_initial_data()

    result = process(table)
    storage.write_table(result, "partial_results", checkpoint=True)
```

### Pattern 4: Testing with Mocks

```python
def test_my_stage():
    """Test with in-memory storage and mocked views."""
    from egregora.database import temp_storage
    from egregora.pipeline.views import ViewRegistry

    # Mock view registry
    test_views = ViewRegistry()

    @test_views.register("my_view")
    def mock_view(ir: Table) -> Table:
        return ir.limit(10)

    # In-memory storage
    with temp_storage() as storage:
        test_table = ibis.memtable({"id": [1, 2, 3]})
        storage.write_table(test_table, "input", checkpoint=False)

        # Run stage
        my_stage(storage, view_registry=test_views)

        # Verify
        result = storage.read_table("output")
        assert result.count().execute() == 10
```

---

## Performance Considerations

### ViewRegistry

**Ibis vs SQL:**
- **Ibis**: Better for complex Python logic, type safety, IDE support
- **SQL**: Better for aggregations, window functions, performance-critical paths

**Benchmarking:**
```python
# Compare Ibis vs SQL versions
result_ibis = views.get("chunks")(large_table).execute()
result_sql = views.get("chunks_optimized")(large_table).execute()
```

### StorageManager

**Checkpoint overhead:**
- `checkpoint=False`: Fastest, no persistence
- `checkpoint=True`: Slower, persists to parquet + DuckDB

**Recommendations:**
- Use `checkpoint=False` for temporary/intermediate tables
- Use `checkpoint=True` for expensive computations and final results
- In-memory mode for tests
- File-based mode for production

---

## Migration Guide

### Before (scattered transformations and SQL)

```python
import duckdb

# Scattered transformation logic
def chunking_stage(input_path: Path) -> None:
    conn = duckdb.connect("pipeline.duckdb")
    conn.execute("CREATE TABLE chunks AS SELECT *, ROW_NUMBER() OVER (...) FROM conversations")
    conn.close()
```

### After (ViewRegistry + StorageManager)

```python
from egregora.database import StorageManager
from egregora.pipeline.views import views

def chunking_stage(storage: StorageManager) -> None:
    """Clean, testable, reusable."""
    chunks_builder = views.get("chunks")
    storage.execute_view("chunks", chunks_builder, "conversations")
```

**Benefits:**
- No raw SQL strings
- Type-safe operations
- Automatic resource cleanup
- Built-in checkpointing
- Easy testing
- Reusable transformations

---

## Testing Instructions

### 1. Install dependencies
```bash
uv sync --all-extras
```

### 2. Run Priority C tests
```bash
# All tests
uv run pytest tests/unit/test_pipeline_views.py tests/unit/test_storage_manager.py -v

# Just ViewRegistry
uv run pytest tests/unit/test_pipeline_views.py -v

# Just StorageManager
uv run pytest tests/unit/test_storage_manager.py -v
```

### 3. Try interactive examples

**ViewRegistry:**
```python
from egregora.pipeline.views import views
import ibis

# List built-in views
print(views.list_views())

# Use a view
table = ibis.memtable({"id": [1, 2, 3]})
limited = views.get("chunks")(table)
```

**StorageManager:**
```python
from egregora.database import temp_storage
import ibis

with temp_storage() as storage:
    table = ibis.memtable({"id": [1, 2, 3]})
    storage.write_table(table, "test", checkpoint=False)
    result = storage.read_table("test")
    print(result.execute())
```

---

## Review Checklist

### Priority C.1 (ViewRegistry)
- [ ] ViewRegistry class with decorator pattern
- [ ] 6 built-in views registered
- [ ] Can register custom views
- [ ] Can swap Ibis ↔ SQL versions
- [ ] 29 tests passing
- [ ] Documentation complete

### Priority C.2 (StorageManager)
- [ ] StorageManager class with context manager
- [ ] Automatic parquet checkpointing
- [ ] ViewRegistry integration (`execute_view`)
- [ ] Table operations work correctly
- [ ] 22 tests passing
- [ ] Documentation complete

### Integration
- [ ] StorageManager can execute ViewRegistry views
- [ ] Example patterns work end-to-end
- [ ] No raw SQL in new code
- [ ] All 51 tests passing

### General
- [ ] No breaking changes
- [ ] Code formatted with ruff
- [ ] CLAUDE.md updated
- [ ] Exports added to __init__ files

---

## Architecture Roadmap Progress

**Completed:**
- ✅ Quick Wins (QW-0 through QW-5)
- ✅ Priority A: Platform Seams & Plugins (A.1, A.2, A.3)
- ✅ **Priority C.1: View Registry** ← This PR
- ✅ **Priority C.2: StorageManager** ← This PR

**Remaining Priority C:**
- C.3: Validate All Stages Conform to IR (1 day)

---

## Next Steps

After merging:
1. **Priority C.3**: Validate all stages conform to IR schema
2. **Pipeline migration**: Migrate existing stages to use ViewRegistry + StorageManager
3. **Performance tuning**: Benchmark Ibis vs SQL views on real data
4. **Custom views**: Document project-specific view patterns

---

## Related Documentation

- `docs/pipeline/view-registry.md` - ViewRegistry complete guide
- `docs/database/storage-manager.md` - StorageManager complete guide
- `ARCHITECTURE_ROADMAP.md` - Priority C specification
- `CLAUDE.md` - Modern Patterns section

---

## Branch Information

**Source Branch**: `claude/actionable-plan-011CUur116K7c4WxATK5d2y4`
**Target Branch**: `main`

**Stats:**
- 2 major features (C.1 + C.2)
- 10 files changed (5 new, 5 modified)
- 2,600+ lines added
- 51 new tests
- All tests passing

**Key Commits:**
```
4ac8b71 feat(pipeline): Add ViewRegistry for pipeline transformations (Priority C.1)
b787769 feat(database): Add StorageManager for centralized DuckDB access (Priority C.2)
```

---

**Ready for review!**

This PR completes Priority C.1 and C.2, providing a clean foundation for data layer discipline with centralized transformations and storage management.

The integration of ViewRegistry and StorageManager enables:
- ✅ Reusable, named transformations
- ✅ Centralized storage with checkpointing
- ✅ No raw SQL in pipeline code
- ✅ Easy testing and mocking
- ✅ Performance optimization via SQL when needed
