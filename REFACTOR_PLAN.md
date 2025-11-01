# Egregora Refactor Plan: Unified Data Contract & DAG Architecture

## Executive Summary

**Goal**: Unify on a single DuckDB database with centralized schemas and declarative DAG-based pipeline stages.

**Impact**: Improves correctness (deterministic outputs), speed (single DB connection), and simplicity (one source of truth for schemas).

**Effort**: 4 phases, each shippable independently. Estimated 2-4 weeks total.

**Risk**: Low - each phase is backwards-compatible until final cutover.

---

## Why This Refactor

### Current Pain Points

1. **Schema Drift**: `RankingStore` defines tables via raw SQL instead of centralized Ibis schemas
2. **Multiple Databases**: `rankings.duckdb` separate from main pipeline DB
3. **Scattered Logic**: Batching and timezone normalization duplicated across stages
4. **Inconsistent Patterns**: RAG follows shared schema approach; ranking doesn't

### Target State

- **One Database**: All pipeline data (messages, enrichments, RAG, rankings) in single DuckDB file
- **One Schema Source**: All table definitions in `src/egregora/core/database_schema.py`
- **DAG Stages**: Each pipeline stage as materialized view with explicit dependencies
- **Shared Utilities**: Canonical batching and timezone handling

---

## Phase 1: Contract First

**Goal**: Centralize all schema definitions and consolidate databases.

### Tasks

#### 1.1 Add Ranking Schemas to Central Schema Module

**File**: `src/egregora/core/database_schema.py`

- [ ] Define `ELO_RATINGS_SCHEMA` as Ibis schema
  - Columns: `post_id`, `rating`, `num_comparisons`, `last_updated`
  - Match current `RankingStore.create_tables()` DDL
- [ ] Define `ELO_COMPARISONS_SCHEMA` (if tracking comparison history)
  - Columns: `comparison_id`, `winner_id`, `loser_id`, `timestamp`
- [ ] Add schemas to `__all__` export

**Acceptance**:
```python
# Can import and use schemas
from egregora.core.database_schema import ELO_RATINGS_SCHEMA
assert "post_id" in ELO_RATINGS_SCHEMA.names
```

#### 1.2 Update RankingStore to Use Central Schemas

**File**: `src/egregora/knowledge/ranking/store.py`

- [ ] Replace `create_tables()` raw SQL with `create_table_if_not_exists()`
  - Use `ELO_RATINGS_SCHEMA` from core module
  - Remove hardcoded DDL strings
- [ ] Update `_ensure_tables()` to use Ibis table creation helpers
- [ ] Verify all queries still work with new schema definitions

**Before**:
```python
def create_tables(self):
    self.conn.execute("""
        CREATE TABLE IF NOT EXISTS elo_ratings (
            post_id TEXT PRIMARY KEY,
            rating DOUBLE,
            ...
        )
    """)
```

**After**:
```python
from egregora.core.database_schema import ELO_RATINGS_SCHEMA, create_table_if_not_exists

def create_tables(self):
    create_table_if_not_exists(self.conn, "elo_ratings", ELO_RATINGS_SCHEMA)
```

#### 1.3 Consolidate rankings.duckdb into Main Database

**Files**:
- `src/egregora/orchestration/database.py`
- `src/egregora/knowledge/ranking/store.py`
- `src/egregora/config/model.py` (if DB path is configurable)

- [ ] Add `rankings_db_path` parameter to database connection manager
  - Default to same DB as main pipeline
  - Support override for backwards compatibility during transition
- [ ] Update `RankingStore.__init__()` to accept shared connection
- [ ] Create migration script to copy existing `rankings.duckdb` into main DB
  - Script: `scripts/migrate_rankings_db.py`
  - Handle table name conflicts (prefix with `elo_` if needed)
- [ ] Update all ranking imports to use unified connection

**Migration Script**:
```python
# scripts/migrate_rankings_db.py
"""Migrate rankings.duckdb into main pipeline database."""
import duckdb
from pathlib import Path

def migrate(old_rankings_db: Path, main_db: Path):
    # Attach old DB and copy tables
    conn = duckdb.connect(str(main_db))
    conn.execute(f"ATTACH '{old_rankings_db}' AS old_rankings")
    conn.execute("CREATE TABLE elo_ratings AS SELECT * FROM old_rankings.elo_ratings")
    conn.execute("DETACH old_rankings")
```

- [ ] Document migration in `CLAUDE.md` under "Database Management"
- [ ] Add warning if old `rankings.duckdb` found (point to migration script)

#### 1.4 Update Tests

**Files**: `tests/knowledge/ranking/test_store.py`

- [ ] Update tests to use centralized schemas
- [ ] Verify schema parity (old DDL == new Ibis schema)
- [ ] Add test for unified DB connection
- [ ] Property test: same queries return same results before/after

**Test Cases**:
```python
def test_schema_parity():
    """Ensure new Ibis schema matches old DDL structure."""
    # Compare column names, types, constraints

def test_unified_db_connection():
    """Ranking operations work with shared DB connection."""
    # Create tables, insert ratings, query - all via one connection
```

### Phase 1 Acceptance Criteria

- [ ] All schemas defined in `core/database_schema.py` (no raw DDL elsewhere)
- [ ] `RankingStore` uses `create_table_if_not_exists()` helper
- [ ] Single DuckDB file contains messages + RAG + rankings
- [ ] All existing tests pass
- [ ] Migration script tested on real `rankings.duckdb` file

---

## Phase 2: Shared Utilities

**Goal**: Centralize batching and timezone logic to eliminate duplication and edge cases.

### Tasks

#### 2.1 Create Canonical Batching Utility

**File**: `src/egregora/utils/batching.py` (new file)

- [ ] Implement `batch_table(table, batch_size, order_by)` using Ibis
  - Returns iterator of table slices
  - Uses `.order_by(...).limit(batch_size, offset=offset)`
  - Replaces row_number window logic
- [ ] Add property tests for exact coverage (no gaps, no overlaps)
- [ ] Document why this is preferred over window functions

**Implementation**:
```python
from typing import Iterator
import ibis
from ibis.expr.types import Table

def batch_table(
    table: Table,
    batch_size: int,
    order_by: list[str]
) -> Iterator[Table]:
    """
    Yield batches of table using stable ordering.

    Preferred over row_number windowing because:
    - Simpler mental model
    - No custom column pollution
    - DuckDB optimizer friendly
    """
    offset = 0
    while True:
        batch = (
            table
            .order_by(order_by)
            .limit(batch_size, offset=offset)
        )
        # Execute to check if empty
        batch_data = batch.execute()
        if len(batch_data) == 0:
            break
        yield batch
        offset += batch_size
```

**Property Tests**:
```python
@given(st.lists(st.integers()), st.integers(min_value=1, max_value=100))
def test_batch_coverage(rows, batch_size):
    """All rows appear exactly once across batches."""
    table = ibis.memtable({"id": rows})
    batched_ids = []
    for batch in batch_table(table, batch_size, ["id"]):
        batched_ids.extend(batch.execute()["id"].tolist())
    assert sorted(batched_ids) == sorted(rows)
```

#### 2.2 Replace Existing Batching Logic

**Files to Update**:
- `src/egregora/augmentation/enrichment/batch.py`
- Any other files using row_number batching

- [ ] Replace window function batching with `batch_table()`
- [ ] Update `_iter_table_record_batches()` to use new utility
- [ ] Remove custom row_number column logic
- [ ] Verify batch sizes match expectations in tests

**Before**:
```python
# Complex windowing with temp columns
batch_col = table.mutate(
    _batch_id=ibis.row_number().over(order_by=["timestamp"]) // batch_size
)
for batch_id in range(num_batches):
    yield batch_col.filter(batch_col._batch_id == batch_id)
```

**After**:
```python
from egregora.utils.batching import batch_table
for batch in batch_table(table, batch_size, order_by=["timestamp"]):
    yield batch
```

#### 2.3 Centralize Timezone Normalization

**File**: `src/egregora/utils/normalization.py` (new file)

- [ ] Create `normalize_timestamps(table)` function
  - Ensures all timestamp columns are UTC scale-9
  - Uses `ensure_message_schema()` under the hood
  - Validates timezone consistency
- [ ] Add to pipeline entry points (ingestion, augmentation)
- [ ] Document timezone contract in `CLAUDE.md`

**Implementation**:
```python
def normalize_timestamps(table: Table, timezone: str = "UTC") -> Table:
    """
    Normalize all timestamp columns to UTC with scale-9 precision.

    This is the canonical entry point for timezone handling.
    All downstream stages assume UTC timestamps.
    """
    from egregora.core.database_schema import ensure_message_schema
    return ensure_message_schema(table, timezone=timezone)
```

**Usage at Pipeline Entry**:
```python
# In orchestration/pipeline.py
def run_pipeline(conversations: Table) -> None:
    # Normalize immediately after ingestion
    conversations = normalize_timestamps(conversations, timezone="UTC")
    # ... rest of pipeline
```

#### 2.4 Update Tests

- [ ] Add tests for `batch_table()` edge cases (empty table, batch_size > table size)
- [ ] Add tests for timezone normalization idempotency
- [ ] Update existing tests to use new utilities

### Phase 2 Acceptance Criteria

- [ ] `batch_table()` passes property tests (no gaps, no overlaps)
- [ ] All pipeline stages use `batch_table()` (no custom batching)
- [ ] Timezone normalization happens once at ingestion
- [ ] All tests pass with new utilities
- [ ] Performance parity or improvement over old batching

---

## Phase 3: Views Over Steps

**Goal**: Express pipeline stages as Ibis views/materialized tables instead of imperative transforms.

### Tasks

#### 3.1 Define Stage Views in Schema Module

**File**: `src/egregora/core/database_schema.py`

- [ ] Add `PIPELINE_STAGES` enum or config
  - `INGESTED_MESSAGES` (raw parsed data)
  - `ANONYMIZED_MESSAGES` (post-privacy)
  - `ENRICHED_MESSAGES` (post-augmentation)
  - `KNOWLEDGE_CONTEXT` (post-RAG retrieval)
- [ ] Define view creation helpers
  - `create_stage_view(conn, stage_name, query)`
  - `materialize_stage(conn, stage_name, query)`

**Example**:
```python
from enum import Enum

class PipelineStage(str, Enum):
    INGESTED = "ingested_messages"
    ANONYMIZED = "anonymized_messages"
    ENRICHED = "enriched_messages"
    KNOWLEDGE = "knowledge_context"

def create_stage_view(
    conn: ibis.BaseBackend,
    stage: PipelineStage,
    source_table: Table
) -> None:
    """Create or replace a pipeline stage view."""
    conn.create_view(stage.value, source_table, overwrite=True)
```

#### 3.2 Refactor Augmentation as Views

**File**: `src/egregora/augmentation/enrichment/core.py`

- [ ] Change `enrich_conversations()` to return Ibis expression (not executed)
- [ ] Keep `replace_media_mentions()` but track outputs in table
  - Add `media_files` table with columns: `media_id`, `original_path`, `site_path`, `description`
  - Media extraction outputs deterministic table rows
- [ ] Create `ENRICHED_MESSAGES` view from enrichment query
- [ ] Ensure schema compliance via `ensure_message_schema()` in view definition

**Current (Imperative)**:
```python
def enrich_conversations(table: Table) -> Table:
    enriched = _add_enrichments(table)  # Side effects
    result = replace_media_mentions(enriched)  # File operations
    return result
```

**Target (Declarative)**:
```python
def define_enrichment_view(source_table: Table) -> Table:
    """Define enrichment as Ibis expression (lazy)."""
    enriched = _add_enrichment_columns(source_table)
    # Media handling becomes join with media_files table
    with_media = enriched.join(media_files, ...)
    return ensure_message_schema(with_media)

# In pipeline:
conn.create_view("enriched_messages", define_enrichment_view(anonymized))
```

#### 3.3 Refactor Media Pipeline as Table Outputs

**Files**:
- `src/egregora/augmentation/media.py`
- `src/egregora/core/database_schema.py` (add `MEDIA_FILES_SCHEMA`)

- [ ] Define `MEDIA_FILES_SCHEMA`
  - Columns: `media_id`, `message_timestamp`, `original_filename`, `site_relative_path`, `description`, `pii_redacted`
- [ ] Change media extraction to write to `media_files` table
  - Deterministic `media_id` (hash of original path + timestamp)
  - Track PII redaction status
- [ ] Link rewriting uses join instead of file scanning
- [ ] Add `media_files` table to unified DB

**Schema**:
```python
MEDIA_FILES_SCHEMA = ibis.schema({
    "media_id": "string",           # Deterministic hash
    "message_timestamp": "timestamp(9, 'UTC')",
    "original_filename": "string",
    "site_relative_path": "string", # e.g., "assets/media/abc123.jpg"
    "description": "string",        # LLM-generated
    "pii_redacted": "boolean",      # Placeholder applied?
})
```

#### 3.4 Update RAG to Use Views

**File**: `src/egregora/knowledge/rag/store.py`

- [ ] RAG indexing consumes `ENRICHED_MESSAGES` view instead of passed table
- [ ] Chunk generation becomes deterministic query over view
- [ ] No changes needed to RAG logic (already follows pattern)

#### 3.5 Update Tests

- [ ] Test view creation and querying
- [ ] Test media table determinism (same input = same `media_id`)
- [ ] Verify enrichment view matches old imperative output
- [ ] Add tests for PII redaction tracking in media table

### Phase 3 Acceptance Criteria

- [ ] All pipeline stages defined as views or materialized tables
- [ ] Media extraction outputs to `media_files` table
- [ ] `ENRICHED_MESSAGES` view queryable via Ibis
- [ ] No loss of functionality (all old features still work)
- [ ] Tests validate view outputs match old imperative outputs
- [ ] PII redactions tracked explicitly in media table

---

## Phase 4: CLI as DAG Runner

**Goal**: CLI computes dependency graph and materializes only needed stages.

### Tasks

#### 4.1 Define Stage Dependencies

**File**: `src/egregora/orchestration/dag.py` (new file)

- [ ] Create `StageDependency` dataclass
  - `name: PipelineStage`
  - `depends_on: list[PipelineStage]`
  - `materialized: bool` (vs. view)
- [ ] Define full pipeline DAG
  - `INGESTED` → `ANONYMIZED` → `ENRICHED` → `KNOWLEDGE` → `GENERATED`
- [ ] Implement topological sort for execution order
- [ ] Add `needs_refresh(conn, stage)` to check if recomputation needed

**DAG Definition**:
```python
from dataclasses import dataclass
from egregora.core.database_schema import PipelineStage

@dataclass
class StageDependency:
    name: PipelineStage
    depends_on: list[PipelineStage]
    materialized: bool = False

PIPELINE_DAG = [
    StageDependency(PipelineStage.INGESTED, depends_on=[]),
    StageDependency(PipelineStage.ANONYMIZED, depends_on=[PipelineStage.INGESTED]),
    StageDependency(PipelineStage.ENRICHED, depends_on=[PipelineStage.ANONYMIZED], materialized=True),
    StageDependency(PipelineStage.KNOWLEDGE, depends_on=[PipelineStage.ENRICHED]),
]

def topological_sort(dag: list[StageDependency]) -> list[PipelineStage]:
    """Return stages in execution order."""
    # Standard topo sort implementation
```

#### 4.2 Implement DAG Executor

**File**: `src/egregora/orchestration/dag.py`

- [ ] Create `execute_dag(conn, target_stage, force_refresh)` function
  - Computes all upstream dependencies
  - Materializes or refreshes as needed
  - Caches view creation (don't recreate if exists and not stale)
- [ ] Add `materialize_stage(conn, stage)` function
  - Creates table from view (for expensive stages like enrichment)
  - Tracks materialization timestamps

**Implementation**:
```python
def execute_dag(
    conn: ibis.BaseBackend,
    target: PipelineStage,
    force_refresh: bool = False
) -> None:
    """Execute pipeline DAG up to target stage."""
    stages = topological_sort(PIPELINE_DAG)
    stages_to_run = stages[:stages.index(target) + 1]

    for stage_def in stages_to_run:
        if force_refresh or needs_refresh(conn, stage_def.name):
            logger.info(f"Computing stage: {stage_def.name}")
            # Get view definition from registry
            view_query = get_stage_query(stage_def.name)
            if stage_def.materialized:
                materialize_stage(conn, stage_def.name, view_query)
            else:
                create_stage_view(conn, stage_def.name, view_query)
```

#### 4.3 Update CLI Commands

**File**: `src/egregora/orchestration/cli.py`

- [ ] Add `--target-stage` option to `process` command
  - Default: `GENERATED` (run full pipeline)
  - Options: `ingested`, `anonymized`, `enriched`, `knowledge`, `generated`
- [ ] Add `--force-refresh` flag to recompute stages even if cached
- [ ] Convert granular commands to debug subcommands
  - `egregora parse` → `egregora debug run-stage ingested`
  - `egregora group` → `egregora debug run-stage anonymized`
  - Keep for backwards compatibility but mark as debug/advanced

**Updated CLI**:
```python
@app.command()
def process(
    export_path: Path,
    output: Path,
    target_stage: PipelineStage = PipelineStage.GENERATED,
    force_refresh: bool = False,
):
    """Process WhatsApp export through pipeline stages."""
    conn = get_database_connection(output)
    execute_dag(conn, target=target_stage, force_refresh=force_refresh)
```

#### 4.4 Add Observability

**Files**:
- `src/egregora/orchestration/dag.py`
- `src/egregora/utils/logging.py` (if custom logging)

- [ ] Log stage execution times
- [ ] Log stage output row counts
- [ ] Add `egregora debug dag-status` command to show stage freshness
- [ ] Optional: Progress bars for long-running stages

**Example Output**:
```
$ egregora process export.zip --output ./output
[1/5] Ingesting messages... (2.3s, 1,234 rows)
[2/5] Anonymizing authors... (0.5s, 1,234 rows)
[3/5] Enriching content... (45.2s, 1,234 rows) [MATERIALIZED]
[4/5] Building knowledge graph... (3.1s, 456 chunks)
[5/5] Generating posts... (12.3s, 3 posts)
✓ Pipeline complete
```

#### 4.5 Update Tests

- [ ] Test DAG topological sort
- [ ] Test partial execution (stop at intermediate stage)
- [ ] Test force refresh (recomputes even if cached)
- [ ] Test stage freshness detection
- [ ] Integration test: full pipeline via DAG executor

### Phase 4 Acceptance Criteria

- [ ] `execute_dag()` correctly orders and executes stages
- [ ] CLI supports `--target-stage` for partial runs
- [ ] Materialization caching works (doesn't recompute unnecessarily)
- [ ] All old CLI commands still work (backwards compatibility)
- [ ] Stage execution logged with timing and row counts
- [ ] Tests validate DAG execution correctness

---

## Implementation Order

### Recommended Sequence

1. **Week 1: Phase 1** (Contract First)
   - Low risk, high value
   - Unblocks subsequent phases
   - Can ship independently

2. **Week 2: Phase 2** (Shared Utilities)
   - Medium risk (touching core logic)
   - High test coverage needed
   - Immediate correctness benefits

3. **Week 3: Phase 3** (Views Over Steps)
   - Medium-high complexity
   - Most architectural change
   - Enables Phase 4

4. **Week 4: Phase 4** (CLI as DAG Runner)
   - Low risk (mainly orchestration)
   - High UX value
   - Final integration

### Parallel Work Opportunities

- Phase 1.1 (schema definitions) + Phase 2.1 (batching utility) can run in parallel
- Phase 1.4 (tests) can start as soon as Phase 1.2 completes
- Phase 3.3 (media pipeline) can be developed independently of Phase 3.2

---

## Risk Mitigation

### Rollback Plan

Each phase includes:
- Feature flags for gradual rollout
- Backwards compatibility shims
- A/B testing (old vs. new path) in tests

**Example Feature Flag**:
```python
# In config/model.py
USE_UNIFIED_DB: bool = os.getenv("EGREGORA_UNIFIED_DB", "false").lower() == "true"

# In code:
if USE_UNIFIED_DB:
    store = RankingStore(conn=unified_conn)
else:
    store = RankingStore(db_path="rankings.duckdb")
```

### Testing Strategy

1. **Property Tests**: Batching coverage, schema roundtrips
2. **Parity Tests**: Old output == new output for same input
3. **Integration Tests**: Full pipeline runs with real data
4. **Performance Tests**: No regression in query/batch speed

### Migration Safety

- **Database Backups**: Auto-backup before migrations
- **Schema Versioning**: Track schema version in DB metadata table
- **Gradual Cutover**: Run old and new paths in parallel during transition

**Schema Version Table**:
```python
SCHEMA_VERSION_TABLE = ibis.schema({
    "version": "int64",
    "applied_at": "timestamp(9, 'UTC')",
    "description": "string",
})

# Check version before applying migrations
current_version = get_schema_version(conn)
if current_version < REQUIRED_VERSION:
    run_migrations(conn, current_version, REQUIRED_VERSION)
```

---

## Success Metrics

### Correctness

- [ ] **Determinism**: Re-running pipeline yields byte-identical outputs for unchanged inputs
- [ ] **Parity**: Old vs. new ranking queries return same rows on same dataset
- [ ] **No Broken Media**: All media links resolve correctly under site-root paths
- [ ] **PII Tracking**: PII deletions surface as explicit placeholders (no silent failures)

### Performance

- [ ] **Query Speed**: No regression (target: <5% slower, ideally faster)
- [ ] **Batch Processing**: Edge cases handled (empty batches, last batch < batch_size)
- [ ] **Single DB**: Connection overhead reduced (measure with profiling)

### Maintainability

- [ ] **Schema Centralization**: 100% of schemas in `core/database_schema.py` (zero raw DDL)
- [ ] **Code Reduction**: Estimated 15-20% fewer lines (remove duplicate batching/TZ logic)
- [ ] **Test Coverage**: No decrease (target: +5% from new property tests)

---

## Post-Refactor Opportunities

Once this refactor is complete, you unlock:

1. **Incremental Computation**: Re-run only changed stages (checkpoint/resume)
2. **Parallel Stage Execution**: Independent stages run concurrently
3. **Schema Evolution**: Automated migrations via Alembic or similar
4. **Query Optimization**: Single-DB enables cross-stage query pushdown
5. **Monitoring**: Built-in observability (stage timings, row counts, cache hit rates)

---

## Appendix: File Manifest

### New Files

- `src/egregora/utils/batching.py` - Canonical batching utility
- `src/egregora/utils/normalization.py` - Timezone normalization
- `src/egregora/orchestration/dag.py` - DAG definition and executor
- `scripts/migrate_rankings_db.py` - Database migration script

### Modified Files

- `src/egregora/core/database_schema.py` - Add ELO, media, stage schemas
- `src/egregora/knowledge/ranking/store.py` - Use central schemas
- `src/egregora/augmentation/enrichment/core.py` - Declarative views
- `src/egregora/augmentation/enrichment/batch.py` - Use `batch_table()`
- `src/egregora/augmentation/media.py` - Table-based outputs
- `src/egregora/orchestration/cli.py` - DAG-based commands
- `src/egregora/orchestration/pipeline.py` - Use DAG executor

### Test Files

- `tests/utils/test_batching.py` - Batching property tests
- `tests/orchestration/test_dag.py` - DAG execution tests
- `tests/knowledge/ranking/test_store.py` - Schema parity tests
- `tests/augmentation/test_media.py` - Media table determinism tests

---

## Getting Started

### Immediate Next Steps

1. **Review this plan** with team/stakeholders
2. **Create feature branch**: `git checkout -b refactor/unified-dag`
3. **Start with Phase 1.1**: Add ELO schemas to `database_schema.py`
4. **Set up tests**: Create `tests/core/test_schema_parity.py`
5. **Iterate**: Ship Phase 1 before starting Phase 2

### Questions to Resolve Before Starting

- [ ] Which DuckDB file path for unified DB? (default: `{output_dir}/egregora.duckdb`)
- [ ] Keep old `rankings.duckdb` for backwards compat period? (suggest: yes, 1 release)
- [ ] Materialization strategy: always materialize enrichment? (suggest: yes, it's expensive)
- [ ] Feature flag naming convention? (suggest: `EGREGORA_ENABLE_*`)

---

**Last Updated**: 2025-11-01
**Status**: Draft - Ready for Review
**Owner**: TBD
**Reviewers**: TBD
