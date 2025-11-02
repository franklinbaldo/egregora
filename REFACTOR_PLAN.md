# Egregora Refactor Plan: Unified Data Contract & DAG Architecture

**Status**: Phase 1-2 ✅ COMPLETE | Phase 3-4 🚧 IN PROGRESS | Phase 5 ⏳ NOT STARTED

**Last Updated**: 2025-11-02

---

## Executive Summary

**Goal**: Unify on a single DuckDB database with centralized schemas and declarative DAG-based pipeline stages.

**Impact**: Improves correctness (deterministic outputs), speed (single DB connection), and simplicity (one source of truth for schemas).

**Current State**:
- ✅ **Phases 1-2 DONE**: Utilities, schemas, RankingStore refactored
- 🚧 **Phase 4 PARTIAL**: DAG infrastructure exists but NOT WIRED UP to pipeline
- ⏳ **Phase 3 NOT STARTED**: Pipeline stages still imperative, not declarative views
- ⏳ **Phase 5 NOT STARTED**: CLI integration missing

**To Complete**: ~800-1200 lines of code across 3 remaining phases

---

## Why This Refactor

### Current Pain Points

1. **Schema Drift**: ~~`RankingStore` defines tables via raw SQL~~ ✅ FIXED
2. **Multiple Databases**: ~~`rankings.duckdb` separate from main pipeline DB~~ ✅ FIXED
3. **Scattered Logic**: ~~Batching and timezone normalization duplicated~~ ✅ FIXED
4. **Inconsistent Patterns**: ~~RAG follows shared schema; ranking doesn't~~ ✅ FIXED
5. **🚧 Imperative Pipeline**: Stages are still procedural functions, not declarative views
6. **🚧 No Incremental Computation**: Can't resume/skip stages
7. **🚧 DAG Infrastructure Unused**: Well-tested DAG code exists but pipeline doesn't use it

### Target State

- ✅ **One Database**: All pipeline data in single DuckDB file
- ✅ **One Schema Source**: All table definitions in `src/egregora/core/database_schema.py`
- 🚧 **DAG Stages**: Each pipeline stage as materialized view with explicit dependencies (INFRASTRUCTURE READY, NOT INTEGRATED)
- ✅ **Shared Utilities**: Canonical batching and timezone handling

---

## COMPLETED WORK (Phases 1-2)

### ✅ Phase 1: Contract First - DONE

**Files Created/Modified**:
- ✅ `src/egregora/core/database_schema.py` - Added ELO_RATINGS_SCHEMA, ELO_HISTORY_SCHEMA, MEDIA_FILES_SCHEMA, PipelineStage enum
- ✅ `src/egregora/knowledge/ranking/store.py` - Refactored to use central schemas + shared connections
- ✅ `tests/test_ranking_store.py` - 162 lines of tests (all passing)

**Achievements**:
- All schemas centralized in `database_schema.py` (no raw DDL)
- RankingStore supports shared DuckDB connections
- Test coverage for schema parity

### ✅ Phase 2: Shared Utilities - DONE

**Files Created**:
- ✅ `src/egregora/utils/batching.py` - 160 lines, offset-based batching (simpler than row_number)
- ✅ `src/egregora/utils/normalization.py` - 49 lines, canonical timezone handling
- ✅ `tests/test_batching.py` - 202 lines of property tests (all passing)
- ✅ `tests/test_batch.py` - 96 lines of integration tests

**Files Modified**:
- ✅ `src/egregora/augmentation/enrichment/batch.py` - Now uses `batch_table_to_records()`

**Achievements**:
- Cleaner batching (DuckDB optimizer friendly, no temp columns)
- Single source of truth for timestamp normalization
- Property tests ensure correctness (no gaps, no overlaps)

---

## 🚧 INCOMPLETE WORK - WHAT'S NEEDED

### Phase 3: Declarative Pipeline Stages (NOT STARTED)

**Goal**: Refactor imperative pipeline functions into declarative Ibis queries that can be registered as DAG compute functions.

**Current Problem**:
- Pipeline stages in `orchestration/pipeline.py` are procedural Python functions
- They execute immediately and don't return Ibis expressions
- Can't be used with DAG executor which expects `Callable[[conn, upstream_tables], Table]`

**What Needs To Happen**:

#### 3.1 Extract Stage Compute Functions

**File**: `src/egregora/orchestration/stages.py` (NEW FILE)

Create wrapper functions for each pipeline stage that return Ibis table expressions:

```python
"""Pipeline stage compute functions for DAG execution.

Each function takes:
- conn: Ibis connection
- upstream_tables: Dict[PipelineStage, Table] of dependencies

Returns:
- Table: Ibis expression (not executed)
"""

from ibis.expr.types import Table
from ..core.database_schema import PipelineStage
from ..ingestion.parser import parse_whatsapp_zip
from ..privacy.anonymizer import anonymize_authors
from ..augmentation.enrichment.core import enrich_table

def compute_ingested(
    conn,
    upstream_tables: dict[PipelineStage, Table],
    *,
    export_path: Path,
    timezone: str = "UTC"
) -> Table:
    """
    Stage 1: Parse WhatsApp export to CONVERSATION_SCHEMA table.

    This is the only stage with no dependencies (source stage).
    """
    from ..utils.normalization import normalize_timestamps

    # Parse ZIP to Ibis table
    conversations = parse_whatsapp_zip(export_path, backend=conn)

    # Normalize timestamps immediately
    conversations = normalize_timestamps(conversations, timezone=timezone)

    return conversations


def compute_anonymized(
    conn,
    upstream_tables: dict[PipelineStage, Table],
) -> Table:
    """
    Stage 2: Replace real names with deterministic UUIDs.

    Depends on: INGESTED
    """
    ingested = upstream_tables[PipelineStage.INGESTED]

    # Anonymize (this returns Ibis expression, doesn't execute)
    anonymized = anonymize_authors(ingested)

    return anonymized


def compute_enriched(
    conn,
    upstream_tables: dict[PipelineStage, Table],
    *,
    model_config: ModelConfig,
    enable_url: bool = True,
    enable_media: bool = True,
    max_enrichments: int = 50,
) -> Table:
    """
    Stage 3: Add LLM descriptions for URLs and media.

    Depends on: ANONYMIZED

    NOTE: This stage is EXPENSIVE (LLM calls), so it's materialized.
    """
    anonymized = upstream_tables[PipelineStage.ANONYMIZED]

    # CHALLENGE: enrich_table() currently executes batches and makes API calls
    # NEED TO: Refactor enrichment to be lazy OR accept that this stage
    # must execute during DAG computation (materialized=True)

    # For now: Execute enrichment during compute (expensive but necessary)
    enriched = enrich_table(
        anonymized,
        posts_dir=Path("temp"),  # FIXME: Need to pass this in
        model_config=model_config,
        enable_url=enable_url,
        enable_media=enable_media,
        max_enrichments=max_enrichments
    )

    return enriched


# CONTINUE for other stages: KNOWLEDGE, GENERATED...
```

**Tasks**:
- [ ] Create `src/egregora/orchestration/stages.py`
- [ ] Implement `compute_ingested()` - wraps `parse_whatsapp_zip()`
- [ ] Implement `compute_anonymized()` - wraps `anonymize_authors()`
- [ ] Implement `compute_enriched()` - wraps `enrich_table()` (may need refactoring)
- [ ] Implement `compute_grouped()` - wraps `group_by_period()` (QUESTION: Is this a stage or post-processing?)
- [ ] Implement `compute_knowledge()` - RAG indexing (if declarative)
- [ ] Add tests for each stage function (verify returns Table, not executed)

**Challenges**:
1. **Enrichment is side-effectful** (makes API calls during execution)
   - **Solution**: Mark as `materialized=True` in DAG, accept that it executes during compute
2. **Some stages need context** (export_path, model_config, output directories)
   - **Solution**: Use functools.partial or closure to bind parameters before passing to DAG
3. **Grouping by period** - not clear if this fits DAG model (1 table → N tables)
   - **Solution**: May need to keep grouping outside DAG, apply DAG per-period

#### 3.2 Refactor Existing Functions to Return Expressions (OPTIONAL)

**Goal**: Make core pipeline functions lazy (return Ibis expressions instead of executing).

**Files to potentially modify**:
- `src/egregora/ingestion/parser.py` - `parse_whatsapp_zip()` already returns Table ✅
- `src/egregora/privacy/anonymizer.py` - `anonymize_authors()` - check if lazy
- `src/egregora/augmentation/enrichment/core.py` - `enrich_table()` - EXECUTES (problem)

**For enrichment specifically**:
```python
# Current: enrich_table() executes batches and makes API calls immediately
# Problem: Can't defer execution for DAG

# Option A: Accept enrichment must execute (materialized=True)
# Option B: Refactor to return enrichment plan, execute later
# Option C: Make enrichment a multi-stage DAG (enriched_urls, enriched_media, etc.)

# RECOMMENDATION: Option A for MVP (mark as materialized)
```

**Tasks**:
- [ ] Audit which functions execute vs. return expressions
- [ ] Document which stages MUST materialize (enrichment, RAG, etc.)
- [ ] Ensure all compute functions return Ibis Table (even if executed inside)

#### 3.3 Media Files as Table (OPTIONAL - NICE TO HAVE)

**Goal**: Track media files in `media_files` table instead of file scanning.

**File**: `src/egregora/augmentation/enrichment/media.py`

**Current**: Media extraction creates files, returns mapping dict
**Target**: Media extraction writes to `media_files` table, links via query

**Tasks**:
- [ ] Modify `extract_media()` to INSERT into `media_files` table
- [ ] Update `replace_media_mentions()` to JOIN against table instead of dict
- [ ] Add `media_id` generation (deterministic hash)
- [ ] Test media table determinism (same input = same IDs)

**Benefit**: Better auditability, supports GDPR deletion tracking

**Complexity**: Medium - requires schema migration, not critical for DAG

---

### Phase 4: Complete DAG Integration (PARTIAL - Infrastructure Done, Wiring Missing)

**Current Status**:
- ✅ `src/egregora/orchestration/dag.py` exists (361 lines)
- ✅ DAGExecutor class implemented
- ✅ Topological sorting (Kahn's algorithm)
- ✅ Caching/materialization logic
- ✅ 14/14 tests passing
- ❌ **NOT USED ANYWHERE** - pipeline.py still calls functions directly

**What's Missing**: DAG executor is never instantiated or called in actual pipeline.

#### 4.1 ✅ DAG Infrastructure - DONE

Already exists in `src/egregora/orchestration/dag.py`:
- `StageDependency` dataclass ✅
- `DAGExecutor` class ✅
- `execute_to_stage()` method ✅
- `_topological_sort()` ✅
- `_execute_stage()` ✅

#### 4.2 Define Pipeline DAG

**File**: `src/egregora/orchestration/stages.py` (same file as Phase 3)

Add DAG definition using compute functions from Phase 3:

```python
from .dag import StageDependency, DAGExecutor
from ..core.database_schema import PipelineStage

# Import all compute functions
from .stages import (
    compute_ingested,
    compute_anonymized,
    compute_enriched,
    compute_knowledge,
)

def build_pipeline_dag(
    export_path: Path,
    model_config: ModelConfig,
    timezone: str = "UTC",
    enable_enrichment: bool = True,
) -> list[StageDependency]:
    """
    Build pipeline DAG with all dependencies.

    Parameters are bound to compute functions using closures.
    """
    from functools import partial

    dag = [
        # Stage 1: Ingestion (no dependencies)
        StageDependency(
            stage=PipelineStage.INGESTED,
            depends_on=[],
            materialized=False,  # Fast, can be view
            compute_fn=partial(
                compute_ingested,
                export_path=export_path,
                timezone=timezone
            )
        ),

        # Stage 2: Anonymization
        StageDependency(
            stage=PipelineStage.ANONYMIZED,
            depends_on=[PipelineStage.INGESTED],
            materialized=False,  # Fast transformation
            compute_fn=compute_anonymized
        ),
    ]

    # Stage 3: Enrichment (optional, expensive)
    if enable_enrichment:
        dag.append(
            StageDependency(
                stage=PipelineStage.ENRICHED,
                depends_on=[PipelineStage.ANONYMIZED],
                materialized=True,  # EXPENSIVE - cache results
                compute_fn=partial(
                    compute_enriched,
                    model_config=model_config,
                )
            )
        )

    # More stages...

    return dag
```

**Tasks**:
- [ ] Create `build_pipeline_dag()` function
- [ ] Wire up all compute functions from Phase 3
- [ ] Use `functools.partial` to bind context (export_path, config, etc.)
- [ ] Mark expensive stages as `materialized=True` (enrichment, RAG)
- [ ] Add tests for DAG construction

#### 4.3 🚧 Wire DAG Into Pipeline - CRITICAL MISSING PIECE

**File**: `src/egregora/orchestration/pipeline.py`

**Current**: `_process_whatsapp_export()` is 300+ lines of imperative code

**Target**: Replace with DAG executor call

**Before** (simplified):
```python
def _process_whatsapp_export(export_path, output_dir, ...):
    # Step 1: Parse
    conversations = parse_whatsapp_zip(export_path)

    # Step 2: Anonymize
    conversations = anonymize_authors(conversations)

    # Step 3: Extract media
    media_mapping = extract_media(export_path, output_dir)
    conversations = replace_media_mentions(conversations, media_mapping)

    # Step 4: Enrich
    if enable_enrichment:
        conversations = enrich_table(conversations, ...)

    # Step 5: Group by period
    periods = group_by_period(conversations)

    # Step 6: Generate posts per period
    for period_key, period_table in periods.items():
        write_posts_for_period(period_table, ...)
```

**After** (DAG-based):
```python
def _process_whatsapp_export(
    export_path: Path,
    output_dir: Path,
    model_config: ModelConfig,
    enable_enrichment: bool = True,
    force_refresh: bool = False,
    ...
):
    """Process WhatsApp export using DAG executor."""

    # 1. Setup database connection
    conn = get_or_create_database(output_dir / "egregora.duckdb")

    # 2. Build DAG with context-bound compute functions
    dag = build_pipeline_dag(
        export_path=export_path,
        model_config=model_config,
        timezone=timezone,
        enable_enrichment=enable_enrichment
    )

    # 3. Execute DAG up to enrichment stage
    executor = DAGExecutor(conn, dag)
    results = executor.execute_to_stage(
        target=PipelineStage.ENRICHED,
        force_refresh=force_refresh
    )

    # 4. Log stage execution
    for result in results:
        logger.info(
            f"[{result.stage.value}] "
            f"{'CACHED' if result.was_cached else 'COMPUTED'} "
            f"({result.row_count} rows, {result.duration_seconds:.2f}s)"
        )

    # 5. Get enriched table for downstream processing
    enriched_table = conn.table(PipelineStage.ENRICHED.value)

    # 6. Group by period (not yet DAG-ified)
    periods = group_by_period(enriched_table, period=grouping)

    # 7. Generate posts per period (existing code)
    for period_key, period_table in periods.items():
        write_posts_for_period(
            period_table,
            period_key,
            client,
            batch_client,
            output_dir=site_paths.posts_dir,
            ...
        )
```

**Tasks**:
- [ ] Refactor `_process_whatsapp_export()` to use DAG executor
- [ ] Keep backward compatibility (feature flag or gradual rollout)
- [ ] Handle grouping by period (either as DAG stage or post-processing)
- [ ] Update tests to verify DAG path works
- [ ] Add integration test: full pipeline via DAG

**Challenges**:
1. **Grouping by period** - DAG assumes 1 table → 1 table, but grouping is 1 → N
   - **Solution A**: Keep grouping outside DAG (current approach above)
   - **Solution B**: Make periods separate DAG runs (more complex)
   - **Solution C**: Flatten periods into single table with `period_key` column

2. **Post generation per period** - currently loops over periods
   - **Solution**: Keep loop, but each period gets enriched data from DAG-materialized table

---

### Phase 5: CLI Integration & Observability (NOT STARTED)

**Goal**: Expose DAG controls via CLI, add visibility into stage execution.

#### 5.1 Update CLI Commands

**File**: `src/egregora/orchestration/cli.py`

**New CLI options**:
```bash
# Run full pipeline (default)
egregora process export.zip --output ./site

# Stop at specific stage
egregora process export.zip --output ./site --target-stage enriched

# Force recompute even if cached
egregora process export.zip --output ./site --force-refresh

# Show DAG status
egregora debug dag-status --output ./site
```

**Implementation**:
```python
@app.command()
def process(
    export_path: Path,
    output: Path,
    target_stage: str = "generated",  # ingested|anonymized|enriched|knowledge|generated
    force_refresh: bool = False,
    ...
):
    """Process WhatsApp export through pipeline stages."""

    # Parse stage name to enum
    try:
        target = PipelineStage[target_stage.upper()]
    except KeyError:
        console.print(f"[red]Invalid stage: {target_stage}[/red]")
        console.print(f"Valid stages: {[s.value for s in PipelineStage]}")
        raise typer.Exit(1)

    # Run pipeline with DAG
    _process_whatsapp_export(
        export_path=export_path,
        output_dir=output,
        target_stage=target,
        force_refresh=force_refresh,
        ...
    )

@app.command()
def dag_status(output: Path):
    """Show DAG stage status and freshness."""
    conn = get_database(output / "egregora.duckdb")

    for stage in PipelineStage:
        if stage_exists(conn, stage):
            table = conn.table(stage.value)
            row_count = table.count().execute()
            # TODO: Get materialization timestamp
            print(f"✓ {stage.value:20s} {row_count:8d} rows")
        else:
            print(f"✗ {stage.value:20s} NOT COMPUTED")
```

**Tasks**:
- [ ] Add `--target-stage` parameter to `process` command
- [ ] Add `--force-refresh` flag
- [ ] Implement `egregora debug dag-status` command
- [ ] Update help text to explain stage options
- [ ] Add validation for stage names

#### 5.2 Enhanced Logging & Progress

**Goal**: Show user-friendly progress during pipeline execution.

**Current**: Basic logger.info() messages
**Target**: Rich progress bars, stage timing, row counts

**Implementation**:
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID

def execute_dag_with_progress(
    conn,
    dag: list[StageDependency],
    target: PipelineStage,
    force_refresh: bool = False
):
    """Execute DAG with progress bar."""

    executor = DAGExecutor(conn, dag)
    stages_to_run = executor._get_execution_order(target)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:

        task = progress.add_task(
            f"Pipeline to {target.value}",
            total=len(stages_to_run)
        )

        for i, stage_def in enumerate(stages_to_run, 1):
            progress.update(
                task,
                description=f"[{i}/{len(stages_to_run)}] {stage_def.stage.value}"
            )

            result = executor._execute_stage(stage_def, force_refresh=force_refresh)

            # Log result
            status = "CACHED" if result.was_cached else "COMPUTED"
            progress.console.print(
                f"  ✓ {result.row_count:,} rows in {result.duration_seconds:.2f}s ({status})"
            )

            progress.advance(task)
```

**Tasks**:
- [ ] Add `rich` progress bars for stage execution
- [ ] Log row counts and timing for each stage
- [ ] Show cache hit/miss status
- [ ] Add `--quiet` flag to disable progress bars
- [ ] Color-code stage types (view vs. materialized)

#### 5.3 Debug Commands

**New commands for debugging pipeline**:

```bash
# Show DAG execution order
egregora debug dag-order --target enriched

# Visualize DAG as ASCII graph
egregora debug dag-graph

# Show table schemas
egregora debug show-schema --stage enriched

# Validate database integrity
egregora debug validate-db --output ./site
```

**Tasks**:
- [ ] Implement `dag-order` command (show topological sort)
- [ ] Implement `dag-graph` command (ASCII visualization)
- [ ] Implement `show-schema` command (print table schema)
- [ ] Implement `validate-db` command (check foreign keys, schema compliance)

---

## Implementation Plan - Recommended Order

### Step 1: Phase 3.1 - Extract Stage Compute Functions
**Effort**: 2-3 days
**Files**: Create `src/egregora/orchestration/stages.py`
**Deliverable**: Compute functions for all stages that return Ibis tables

### Step 2: Phase 4.2 - Define Pipeline DAG
**Effort**: 1 day
**Files**: Add `build_pipeline_dag()` to `stages.py`
**Deliverable**: DAG definition with bound compute functions

### Step 3: Phase 4.3 - Wire DAG Into Pipeline
**Effort**: 3-4 days
**Files**: Refactor `orchestration/pipeline.py`
**Deliverable**: Pipeline uses DAG executor (with backward compat)

### Step 4: Integration Testing
**Effort**: 2 days
**Files**: Add end-to-end tests
**Deliverable**: Full pipeline test via DAG executor

### Step 5: Phase 5.1 - CLI Integration
**Effort**: 1-2 days
**Files**: Update `orchestration/cli.py`
**Deliverable**: CLI supports --target-stage, --force-refresh

### Step 6: Phase 5.2 - Logging & Progress
**Effort**: 1 day
**Files**: Add rich progress bars
**Deliverable**: User-friendly pipeline output

### Step 7: Phase 3.3 - Media Files Table (OPTIONAL)
**Effort**: 2-3 days
**Files**: Refactor media extraction
**Deliverable**: Media tracked in database

**Total Estimated Effort**: 10-15 days (2-3 weeks)

---

## Testing Strategy

### Unit Tests (Per Phase)

**Phase 3**:
- [ ] Test each compute function returns Table (not executed)
- [ ] Test compute functions with mock upstream tables
- [ ] Test stage functions handle missing dependencies gracefully

**Phase 4**:
- [ ] Test `build_pipeline_dag()` creates valid dependencies
- [ ] Test DAG executor with pipeline stages (not just toy examples)
- [ ] Test partial execution (stop at intermediate stage)

**Phase 5**:
- [ ] Test CLI parsing of stage names
- [ ] Test --force-refresh recomputes stages
- [ ] Test dag-status command output

### Integration Tests

- [ ] Full pipeline test: export.zip → posts (via DAG)
- [ ] Incremental test: run twice, verify caching works
- [ ] Force refresh test: --force-refresh recomputes all
- [ ] Partial execution test: --target-stage enriched stops early
- [ ] Backward compat test: old pipeline.py code path still works

### Property Tests

- [ ] Same input → same output (determinism)
- [ ] Cached execution == fresh execution (correctness)
- [ ] Stage order is topological (no dependency violations)

---

## Success Metrics

### Correctness

- [ ] **Determinism**: Re-running pipeline yields identical outputs
- [ ] **Parity**: DAG path produces same results as old imperative path
- [ ] **No Regressions**: All existing tests pass with DAG executor

### Performance

- [ ] **Caching Works**: Second run skips already-computed stages
- [ ] **No Slowdown**: DAG overhead < 5% vs. old pipeline
- [ ] **Materialization**: Expensive stages (enrichment) cached correctly

### Usability

- [ ] **Clear Progress**: User sees what stage is running + timing
- [ ] **Partial Runs**: Can stop at intermediate stage for debugging
- [ ] **Resume Support**: Can skip already-computed stages (via caching)

---

## Migration & Rollout

### Backward Compatibility

**Strategy**: Feature flag for gradual rollout

```python
# In cli.py or config
USE_DAG_EXECUTOR = os.getenv("EGREGORA_USE_DAG", "false").lower() == "true"

if USE_DAG_EXECUTOR:
    _process_whatsapp_export_dag(...)  # New DAG path
else:
    _process_whatsapp_export_legacy(...)  # Old imperative path
```

**Rollout phases**:
1. **Alpha**: DAG path behind feature flag, opt-in testing
2. **Beta**: DAG path default, legacy path available via flag
3. **GA**: Remove legacy path after 1-2 releases

### Database Migration

**No migration needed** - DAG uses same DuckDB schema, just different execution path.

**Cleanup**:
- Old materialized stages can be dropped (they'll be recreated)
- Or keep for backward compatibility period

---

## Open Questions & Decisions Needed

### Q1: How to handle period grouping in DAG?

**Current**: `group_by_period()` returns `dict[str, Table]` (1 table → N tables)
**DAG Model**: Assumes 1 table → 1 table per stage

**Options**:
- **A**: Keep grouping outside DAG (simpler, current approach)
- **B**: Flatten periods into single table with `period_key` column
- **C**: Run separate DAG per period (more complex, better parallelism)

**Recommendation**: Start with **Option A**, consider B/C later.

---

### Q2: Should generation (write_posts_for_period) be a DAG stage?

**Current**: Generation loops over periods, calls LLM, writes markdown files (side effects)

**Challenges for DAG**:
- Not a Table → Table transformation
- Has side effects (writes files, makes API calls)
- Output is markdown files, not database table

**Options**:
- **A**: Keep generation outside DAG (current approach)
- **B**: Model generation as table of "post requests" → "generated posts" table
- **C**: Create `GENERATED_POSTS` table with markdown content as column

**Recommendation**: Start with **Option A** (generation stays imperative).

---

### Q3: Feature flag naming convention?

**Proposal**: `EGREGORA_USE_DAG=true`

**Alternative**: `EGREGORA_EXECUTOR=dag` (vs `legacy`)

**Decision**: TBD

---

## Appendix: Current DAG Infrastructure (Already Built)

### Existing Files (From PR #520)

**Core DAG**:
- ✅ `src/egregora/orchestration/dag.py` (361 lines)
  - `StageDependency` dataclass
  - `DAGExecutor` class
  - Topological sorting
  - Stage caching logic

**Utilities**:
- ✅ `src/egregora/utils/batching.py` (160 lines)
- ✅ `src/egregora/utils/normalization.py` (49 lines)

**Schema Updates**:
- ✅ `src/egregora/core/database_schema.py`
  - `PipelineStage` enum
  - `create_stage_view()`, `materialize_stage()` helpers
  - `MEDIA_FILES_SCHEMA`

**Tests**:
- ✅ `tests/test_dag.py` (384 lines, 14 tests, all passing)
- ✅ `tests/test_batching.py` (202 lines)
- ✅ `tests/test_pipeline_stages.py` (222 lines)

**What's Missing**: Integration (Phases 3-5 above)

---

## Files to Create

### New Files Needed

1. `src/egregora/orchestration/stages.py` - Stage compute functions + DAG builder
2. `src/egregora/orchestration/executor.py` - Pipeline-specific executor wrapper (optional)
3. `tests/integration/test_dag_pipeline.py` - End-to-end DAG tests

### Files to Modify

1. `src/egregora/orchestration/pipeline.py` - Wire in DAG executor
2. `src/egregora/orchestration/cli.py` - Add CLI options
3. `src/egregora/ingestion/parser.py` - Ensure returns lazy Table
4. `src/egregora/augmentation/enrichment/core.py` - Document execution model

---

## Next Steps (Immediate Actions)

1. **Review this plan** - Get alignment on approach
2. **Decide on open questions** (Q1-Q3 above)
3. **Create feature branch**: `git checkout -b refactor/complete-dag-integration`
4. **Start with Phase 3.1**: Create `stages.py` with first compute function
5. **Iterate**: Ship incrementally, test frequently

**First Concrete Task**:
```bash
# Create stages.py with ingestion stage
touch src/egregora/orchestration/stages.py

# Write compute_ingested() function
# Test it returns Table without executing
# Add to git and commit
```

---

**Status**: Ready for implementation
**Owner**: TBD
**Reviewers**: TBD
**Target Completion**: 2-3 weeks from start

---

## Appendix B: DAG Libraries - Should We Use One?

### Current Implementation

**Custom DAG** in `src/egregora/orchestration/dag.py`:
- 361 lines of hand-written code
- Kahn's algorithm for topological sorting
- Basic caching/materialization
- 14 unit tests (all passing)

### Alternative: Use Existing DAG Library

**Popular Python DAG Libraries**:

1. **Apache Airflow** ❌
   - **Pros**: Industry standard, mature, web UI, scheduling
   - **Cons**: MASSIVE overkill (requires web server, database, workers), heavy dependency
   - **Verdict**: Too heavyweight for local data pipeline

2. **Prefect** ❌
   - **Pros**: Modern, Python-native, good caching
   - **Cons**: Requires server/cloud, adds complexity
   - **Verdict**: Over-engineered for our use case

3. **Luigi** (by Spotify) ❌
   - **Pros**: Simpler than Airflow, file-based targets
   - **Cons**: Still designed for distributed batch jobs, extra dependency
   - **Verdict**: Adds complexity without clear benefit

4. **Dask** ❌
   - **Pros**: Great for parallel computation, DataFrame-native
   - **Cons**: Focused on parallelism/distributed compute, not pipeline orchestration
   - **Verdict**: Wrong tool for the job

5. **Hamilton** (by Stitch Fix) ⚠️
   - **Pros**: Lightweight, function-based DAG, data-centric, minimal deps
   - **Cons**: Less mature, smaller community
   - **Verdict**: **MOST PROMISING** if we switch

6. **NetworkX** (graph library) ⚠️
   - **Pros**: Python stdlib-adjacent, topological sort built-in, no DAG-specific opinions
   - **Cons**: Just a graph library (no execution, caching, etc.)
   - **Verdict**: Could simplify our topological sort (replace 30 lines with 3)

### Recommendation: **Keep Custom DAG**

**Why?**

1. **Already Built & Tested**: 361 lines, 14 tests passing, works well
2. **No External Deps**: Don't want heavy dependencies for simple orchestration
3. **Perfect Fit**: Designed exactly for our use case (Ibis table transformations)
4. **Learning Value**: Simple, understandable, easy to debug
5. **Flexibility**: Can evolve with our needs without library constraints

**Potential Improvement**: Use NetworkX for topological sorting

```python
# Current: 50 lines of Kahn's algorithm
def _topological_sort(self, stages, stage_to_def):
    in_degree = defaultdict(int)
    adjacency = defaultdict(list)
    # ... 40 more lines ...

# With NetworkX: 5 lines
import networkx as nx

def _topological_sort(self, stages, stage_to_def):
    G = nx.DiGraph()
    for stage in stages:
        stage_def = stage_to_def.get(stage)
        if stage_def:
            for dep in stage_def.depends_on:
                G.add_edge(dep, stage)  # dep → stage
    return list(nx.topological_sort(G))
```

**Trade-off**:
- **Gain**: Simpler code (45 lines → 5 lines), cycle detection, more algorithms
- **Cost**: New dependency (`networkx`), slight performance overhead
- **Verdict**: **Worth it** - NetworkX is widely used, small dep, big simplification

### Decision Matrix

| Library     | Lines Saved | New Deps | Complexity | Verdict |
|-------------|-------------|----------|------------|---------|
| None (current) | 0        | 0        | Low        | ✅ **Default** |
| NetworkX    | ~45         | 1 (small)| Lower      | ✅ **Recommended** |
| Hamilton    | ~200        | 1 (medium)| Medium    | ⚠️ Consider later |
| Airflow     | ~100        | MANY     | VERY HIGH  | ❌ No |
| Prefect     | ~150        | MANY     | HIGH       | ❌ No |

### Implementation Plan with NetworkX

**Phase 0.5: Optional NetworkX Integration**

**Effort**: 1 hour
**Benefit**: Simpler, more maintainable topological sort

**Tasks**:
- [ ] Add `networkx` to `pyproject.toml` dependencies
- [ ] Replace `_topological_sort()` with NetworkX version
- [ ] Update tests (should all still pass)
- [ ] Add cycle detection test (NetworkX gives better error messages)

**Example**:
```python
# src/egregora/orchestration/dag.py

import networkx as nx

class DAGExecutor:
    # ... existing code ...

    def _topological_sort(
        self,
        stages: set[PipelineStage],
        stage_to_def: dict[PipelineStage, StageDependency],
    ) -> list[PipelineStage]:
        """
        Sort stages in topological order using NetworkX.

        Raises:
            nx.NetworkXError: If DAG contains a cycle
        """
        G = nx.DiGraph()

        # Build dependency graph
        for stage in stages:
            stage_def = stage_to_def.get(stage)
            if not stage_def:
                continue

            # Add edges: dependency → stage
            for dep in stage_def.depends_on:
                if dep in stages:
                    G.add_edge(dep, stage)

        # NetworkX topological sort (raises error if cycle detected)
        try:
            return list(nx.topological_sort(G))
        except nx.NetworkXError as e:
            raise ValueError(f"DAG contains a cycle: {e}") from e
```

**Benefits**:
- Simpler code (50 lines → 15 lines)
- Better error messages for cycles
- Access to graph algorithms (if needed later)
- Well-tested library (no bugs in our topo sort)

**Cost**:
- One extra dependency (~500KB)
- Negligible performance difference

**Verdict**: **Do this** - small win, low cost

---

## Final Recommendation

1. **Keep custom DAG executor** - already built, works well, no need for Airflow/Prefect
2. **Use NetworkX for topological sort** - simplifies code, better error messages
3. **Don't add Hamilton/Dask** - not needed for our use case
4. **Re-evaluate in 6 months** - if DAG complexity grows, consider Hamilton

**Action Items**:
- [ ] Add NetworkX to dependencies
- [ ] Refactor `_topological_sort()` to use NetworkX
- [ ] Verify all tests still pass
- [ ] Ship it!

