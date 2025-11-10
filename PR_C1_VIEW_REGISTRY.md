# Pull Request: Priority C.1 - View Registry for Pipeline Transformations

## Title
Priority C.1: View Registry + SQL Stage Views

## Summary

This PR implements **Priority C.1** from the Architecture Roadmap: a centralized view registry for pipeline stage transformations with transparent Ibis ↔ SQL swapping.

**Status**: Complete, tested, documented
**Roadmap Item**: Priority C.1 (Data Layer Discipline)
**Estimated Effort**: 2 days → **Actual: 1 day**

## What's Included

### Core Implementation

**ViewRegistry System:**
- `ViewRegistry` class with decorator-based registration
- `ViewBuilder` type alias: `Callable[[Table], Table]`
- Global singleton `views` registry
- Transparent Ibis ↔ SQL optimization swapping

**Built-in Views (6 total):**
1. `chunks` - Row numbering by thread (Ibis)
2. `chunks_optimized` - Same as chunks but SQL (performance)
3. `messages_with_media` - Filter to media messages
4. `messages_with_text` - Filter to non-empty text
5. `hourly_aggregates` - Hourly statistics
6. `daily_aggregates` - Daily statistics

**Key Features:**
- Reference views by name (loose coupling)
- Easy testing with mocked registries
- Performance optimization via SQL when needed
- Centralized transformation definitions

## Architecture Benefits

**Problems Solved:**
1. **Scattered transformations**: No more duplicated logic across stages
2. **Hard to test**: Can mock registry for unit tests
3. **SQL optimization unclear**: Clear pattern for Ibis → SQL migration
4. **Tight coupling**: Stages reference views by name, not implementation

**Design Principles:**
- Callable view builders (not SQL strings)
- Decorator-based registration
- Global singleton for convenience
- Separate from database materialized views (`database/views.py`)

## Usage Examples

### Register Custom View

```python
from egregora.pipeline.views import views

@views.register("enriched_messages")
def enriched_messages(ir: Table) -> Table:
    """Filter to messages with enriched metadata."""
    return ir.filter(ir.media_description.notnull())
```

### Use View in Pipeline Stage

```python
from egregora.pipeline.views import views

def chunking_stage(ir_table: Table) -> Table:
    """Chunk messages into windows."""
    chunks_builder = views.get("chunks")
    return chunks_builder(ir_table)
```

### Swap Ibis ↔ SQL for Performance

```python
# Development: use Ibis
builder = views.get("chunks")

# Production: use SQL optimization
builder = views.get("chunks_optimized")
```

## Files Added

- `src/egregora/pipeline/views.py` (315 lines)
  - ViewRegistry class
  - ViewBuilder type alias
  - 6 built-in views
  - Global `views` singleton

- `tests/unit/test_pipeline_views.py` (380 lines)
  - 29 comprehensive tests
  - Tests for: registration, retrieval, execution, built-in views
  - All tests passing

- `docs/pipeline/view-registry.md` (450+ lines)
  - Complete usage guide
  - API reference
  - Design patterns
  - Migration guide
  - Comparison with database views

## Files Modified

- `src/egregora/pipeline/__init__.py`
  - Export `ViewRegistry`, `ViewBuilder`, `views`
  - Added View Registry section to module docstring

- `CLAUDE.md`
  - Documented View Registry pattern in "Modern Patterns"
  - Added to Code Structure section
  - Usage guidelines and anti-patterns

## Test Coverage

**Total**: 29 tests (all passing)

**Test Categories:**
- Registry operations (11 tests)
  - Initialization, registration, retrieval, errors
  - List, unregister, clear operations
- View execution (3 tests)
  - Limit, filter, mutation transformations
- Global registry (7 tests)
  - Built-in views registered
  - Singleton behavior
- Common views (5 tests)
  - chunks, media filters, aggregates
- Type compatibility (3 tests)
  - ViewBuilder callable type

**Test Command:**
```bash
uv run pytest tests/unit/test_pipeline_views.py -v
# 29 passed in 3.13s
```

## Breaking Changes

**None** - All changes are additive:
- New module `pipeline/views.py`
- New exports from `pipeline/__init__.py`
- No changes to existing pipeline stages

Existing functionality remains unchanged.

## Comparison with Database Views

Egregora has **two view systems** serving different purposes:

| Feature | Pipeline Views (C.1) | Database Views |
|---------|----------------------|----------------|
| **Module** | `pipeline/views.py` | `database/views.py` |
| **Purpose** | Pipeline transformations | Query optimization |
| **Format** | Callable functions | SQL strings |
| **Storage** | In-memory registry | Materialized in DuckDB |
| **Use case** | Stage composition | Performance caching |

**When to use which:**
- **Pipeline views** (C.1): Stage logic, reusable transformations, testing
- **Database views**: Expensive queries, pre-computed aggregations, caching

## Design Patterns

### Pattern 1: Layered Views

```python
@views.register("base_messages")
def base_messages(ir: Table) -> Table:
    return ir.filter(ir.text.notnull())

@views.register("enriched_messages")
def enriched_messages(ir: Table) -> Table:
    base = views.get("base_messages")(ir)
    return base.filter(base.media_description.notnull())
```

### Pattern 2: SQL for Performance

```python
@views.register("complex_stats_sql")
def complex_stats_sql(ir: Table) -> Table:
    return ir.sql("""
        SELECT
            thread_id,
            COUNT(*) as msg_count,
            COUNT(DISTINCT author_uuid) as unique_authors,
            MAX(ts) - MIN(ts) as thread_duration
        FROM ir
        GROUP BY thread_id
    """)
```

### Pattern 3: Testing with Mocks

```python
def test_my_stage():
    test_views = ViewRegistry()

    @test_views.register("chunks")
    def mock_chunks(ir: Table) -> Table:
        return ir.mutate(chunk_idx=1)

    result = my_stage(test_table, view_registry=test_views)
```

## Performance Considerations

**Ibis vs SQL:**
- **Ibis**: Better for Python logic, type safety, IDE support
- **SQL**: Better for aggregations, window functions, performance-critical paths

**Benchmarking pattern:**
```python
# Compare Ibis vs SQL versions
result_ibis = views.get("chunks")(large_table).execute()
result_sql = views.get("chunks_optimized")(large_table).execute()
```

## Testing Instructions

### 1. Install dependencies
```bash
uv sync --all-extras
```

### 2. Run View Registry tests
```bash
uv run pytest tests/unit/test_pipeline_views.py -v
```

### 3. Verify imports work
```python
from egregora.pipeline import views, ViewRegistry, ViewBuilder

# Check built-in views
print(views.list_views())
# ['chunks', 'chunks_optimized', 'daily_aggregates', ...]
```

### 4. Try a view
```python
import ibis
from egregora.pipeline.views import views

# Create sample table
table = ibis.memtable({"id": [1, 2, 3]}, schema={"id": "int64"})

# Use built-in view (no-op for this simple table)
builder = views.get("messages_with_text")
result = builder(table)
```

## Review Checklist

- [ ] All 29 tests passing
- [ ] View Registry exports from `pipeline/__init__.py`
- [ ] Documentation comprehensive (`docs/pipeline/view-registry.md`)
- [ ] CLAUDE.md updated with View Registry pattern
- [ ] No breaking changes
- [ ] Built-in views work correctly
- [ ] Code formatted with ruff

## API Reference

### ViewRegistry

```python
class ViewRegistry:
    def __init__(self) -> None: ...
    def register(self, name: str) -> Callable: ...
    def register_function(self, name: str, func: ViewBuilder) -> None: ...
    def get(self, name: str) -> ViewBuilder: ...
    def has(self, name: str) -> bool: ...
    def list_views(self) -> list[str]: ...
    def unregister(self, name: str) -> None: ...
    def clear(self) -> None: ...
```

### ViewBuilder Type

```python
ViewBuilder = Callable[[Table], Table]
```

### Global Registry

```python
from egregora.pipeline.views import views

# Pre-registered with 6 built-in views
views.list_views()  # ['chunks', 'chunks_optimized', ...]
```

## Architecture Roadmap Progress

**Completed:**
- ✅ Quick Wins (QW-0 through QW-5)
- ✅ Priority A: Platform Seams & Plugins (A.1, A.2, A.3)
- ✅ **Priority C.1: View Registry + SQL Stage Views** ← This PR

**Remaining Priority C:**
- C.2: StorageManager + No Raw SQL (2 days)
- C.3: Validate All Stages Conform to IR (1 day)

## Next Steps

After merging:
1. **Priority C.2**: Implement StorageManager for centralized DuckDB access
2. **Pipeline stages**: Migrate existing transformations to use view registry
3. **Performance tuning**: Benchmark Ibis vs SQL views on real data
4. **Custom views**: Document project-specific view patterns

## Related Documentation

- `docs/pipeline/view-registry.md` - Complete usage guide
- `ARCHITECTURE_ROADMAP.md` - Priority C.1 specification
- `src/egregora/database/views.py` - Database materialized views (different system)

---

## Branch Information

**Source Branch**: `claude/actionable-plan-011CUur116K7c4WxATK5d2y4`
**Target Branch**: `main`

**Stats**:
- 1 commit (Priority C.1)
- 5 files changed
- 1,153 insertions, 1 deletion
- 29 new tests
- All tests passing

**Commit:**
```
4ac8b71 feat(pipeline): Add ViewRegistry for pipeline transformations (Priority C.1)
```

---

**Ready for review!**

This PR completes Priority C.1, providing a clean foundation for pipeline stage transformations with flexible optimization strategies.
