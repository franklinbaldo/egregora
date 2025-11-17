# Infrastructure Simplification Plan

**Created**: 2025-11-17
**Status**: DRAFT
**Priority**: P1 - Critical for alpha stability

## Executive Summary

This document outlines a systematic plan to reduce infrastructure complexity in Egregora while maintaining (or improving) observability and developer experience. The goal is to embrace the **alpha mindset**: favor simplicity over premature optimization, reduce moving parts, and make the codebase easier to reason about.

**Key Metrics**:
- **Estimated LOC reduction**: ~1,200+ lines
- **Files to remove**: ~8 files
- **Complexity reduction**: 6 major simplifications
- **Breaking changes**: Minimal (mostly internal infrastructure)

## Philosophy: Alpha Mindset

> "We're paying complexity tax without really cashing the benefits."

For an alpha, local-first tool with a single developer (or very small team):
- **Simple > Robust**: Choose the simpler solution until complexity is justified by real needs
- **One Truth > Multiple Models**: Avoid maintaining parallel representations of the same data
- **Battle-Tested > Custom**: Prefer standard tools (ruff, pytest) over homegrown infrastructure
- **Explicit > Magic**: Clear, simple code beats clever abstractions

## Proposed Simplifications

### 1. Tracking Infrastructure: Unify to Single Model

**Problem**: Three overlapping tracking systems for the same data.

**Current State**:
- `runs` table (stateful, UPDATE-based)
- `run_events` table (event-sourced, append-only)
- `lineage` table (DAG edges for multi-stage dependencies)
- Per-window tracking in `transformations/windowing.py`

**Complexity Indicators**:
- ~500 LOC maintaining parallel models
- Two sources of truth for run status
- Extra observability code wrapped in try/except to prevent pipeline failures
- No current workflows consume the full richness of event-sourcing or DAG lineage

**Proposal**: Keep only `runs` table, simplify lineage.

**Changes**:
1. **Remove `run_events` entirely**
   - Drop `RUN_EVENTS_SCHEMA` and `RUN_EVENTS_TABLE_DDL`
   - Delete `create_run_events_table()` and related functions
   - Remove event-writing logic from `windowing.py`

2. **Simplify lineage tracking**
   - **Option A** (recommended): Add `parent_run_id` column to `runs` (single-parent only)
   - **Option B**: Keep `lineage` table but comment out writes until multi-parent DAG is needed
   - Remove `record_lineage()` from hot path

3. **Consolidate per-window tracking**
   - Replace per-window run events with aggregate metrics in `runs.rows_out`
   - Store `num_windows`, `total_posts`, `total_profiles` as JSON in `runs.attrs` or custom columns

**Benefits**:
- ✅ Single source of truth for run status
- ✅ Simpler mental model: one row per stage execution
- ✅ ~300 LOC removed
- ✅ Same or better observability for current use cases

**Implementation Steps**:
1. Add `attrs JSON` column to `runs` table for extensibility
2. Update `run_stage_with_tracking()` to aggregate window metrics
3. Remove `run_events` table creation and writes
4. Update `egregora runs` CLI to work with `runs` table only
5. Archive lineage logic with TENET-BREAK comment for future restoration

**Estimated Impact**: 🔥🔥🔥 High (major complexity reduction)

---

### 2. IR Schema: Single Source of Truth

**Problem**: Three representations of the same schema (SQL + JSON + Python).

**Current State**:
- `schema/ir_v1.sql` - Canonical SQL definition
- `schema/ir_v1.json` - JSON lockfile with metadata
- `src/egregora/database/ir_schema.py:IR_MESSAGE_SCHEMA` - Ibis schema
- Comments warning about multi-step update process

**Complexity Indicators**:
- Must update 3 files + run validation script on any schema change
- Risk of drift between representations
- "LOCKED" language discourages necessary iteration

**Proposal**: Make Python (Ibis) the canonical source, generate the rest.

**Changes**:
1. **Make `IR_MESSAGE_SCHEMA` in Python canonical**
   - This is what the code actually uses
   - Easier to keep in sync (type-checked, imported)

2. **Add `dev_tools/generate_ir_schema.py`**
   - Reads `IR_MESSAGE_SCHEMA` from Python
   - Generates `schema/ir_v1.sql` (DDL)
   - Optionally generates `schema/ir_v1.json` (for docs/external tools)
   - Run in CI to verify schemas stay in sync

3. **Relax "LOCKED" posture**
   - Remove numbered checklist from SQL file
   - Keep comment about version bumping, but make it lightweight
   - Trust that tests will catch adapter breakage

4. **Optional: Remove JSON lockfile**
   - If not consumed by external tools, delete it
   - Move column descriptions to `docs/architecture/ir-v1-spec.md`

**Benefits**:
- ✅ One place to change IR schema
- ✅ Automatic consistency (generated files)
- ✅ Easier iteration during alpha
- ✅ ~100 LOC removed (validation scripts, JSON maintenance)

**Implementation Steps**:
1. Create `dev_tools/generate_ir_schema.py`
2. Add pre-commit hook or CI check to verify schemas match
3. Update `CLAUDE.md` to reflect new workflow
4. Remove `scripts/check_ir_schema.py` if redundant
5. Decide on JSON lockfile (keep vs. remove)

**Estimated Impact**: 🔥🔥 Medium-High (reduces friction)

---

### 3. Validation: Drop Legacy Compatibility

**Problem**: `validate_stage` decorator supports both modern and legacy patterns.

**Current State**:
- `validation.py:validate_stage` detects method vs. function
- Supports both `Table` return and `.data` attribute (StageResult-like)
- Comment explicitly mentions "PipelineStage abstraction has been removed"

**Complexity Indicators**:
- Extra code paths for compatibility with deleted abstractions
- Fuzzy type signature (returns Table or StageResult-like)
- Validation logic more complex than necessary

**Proposal**: Hard-cut to modern functional API.

**Changes**:
1. **Simplify `validate_stage` signature**
   - Assume `func(data: Table, **kwargs) -> Table`
   - Remove `is_method` / `data_index` detection
   - Remove `.data` attribute fallback

2. **Delete any remaining `StageResult`-like classes**
   - Search for classes with `.data` attribute pattern
   - Fix call sites to use plain `Table` returns

3. **Update decorator to simple wrapper**
   ```python
   def validate_stage(func: Callable[..., Table]) -> Callable[..., Table]:
       @wraps(func)
       def wrapper(data: Table, **kwargs: Any) -> Table:
           validate_ir_schema(data)  # Input
           result = func(data, **kwargs)
           validate_ir_schema(result)  # Output
           return result
       return wrapper
   ```

**Benefits**:
- ✅ Clear contract: `Table → Table`
- ✅ Easier to understand and debug
- ✅ ~50 LOC removed from decorator
- ✅ No ghost compatibility for deleted patterns

**Implementation Steps**:
1. Search for any `.data` attribute access in codebase
2. Update any remaining class-based stages to functional style
3. Simplify `validate_stage` decorator
4. Update tests to match new signature
5. Update docstrings to remove legacy mentions

**Estimated Impact**: 🔥 Medium (code clarity, fewer surprises)

---

### 4. Fingerprinting: Choose Lightweight Approach

**Problem**: Expensive fingerprinting with fuzzy semantics.

**Current State**:
- `fingerprint_table()` sorts entire table by all columns
- Samples 1,000 rows and converts to PyArrow
- Fingerprint not tied to full input (two tables with same head differ only in tail)
- Checkpointing logic not yet fully robust

**Complexity Indicators**:
- Sorting + Arrow conversion expensive on large IR tables
- Sampling means fingerprint is approximate, not deterministic
- Current resume logic doesn't depend heavily on fingerprints

**Proposal**: Replace with cheap aggregate-based fingerprinting.

**Changes**:

**Option A: Aggregate Statistics** (Recommended)
```python
def fingerprint_table(table: Table) -> str:
    """Generate cheap fingerprint from table statistics."""
    stats = table.aggregate([
        table.count().name("row_count"),
        table.ts.min().name("min_ts"),
        table.ts.max().name("max_ts"),
        table.text.length().sum().name("total_text_len"),
    ]).execute()

    # Combine stats with code_ref and config_hash
    stats_str = f"{stats.row_count}|{stats.min_ts}|{stats.max_ts}|{stats.total_text_len}"
    return f"sha256:{hashlib.sha256(stats_str.encode()).hexdigest()}"
```

**Option B: Timestamp-Based Checkpointing**
- Replace `input_fingerprint` with `last_processed_ts` per (tenant, stage)
- Store in `runs` table or separate checkpoint file
- Filter `IR` by `ts > last_processed_ts` and update after stage

**Recommendation**: Start with Option A (keeps fingerprinting but makes it cheap), migrate to Option B if timestamp-based proves simpler.

**Benefits**:
- ✅ Orders of magnitude faster (single aggregate query)
- ✅ Still detects input changes (row count, time bounds, content size)
- ✅ Clearer semantics: "did the input change substantially?"
- ✅ ~100 LOC simpler (remove sorting, Arrow conversion)

**Implementation Steps**:
1. Add new `fingerprint_table_fast()` function
2. Update `run_stage_with_tracking()` to use fast version
3. Run tests to verify checkpointing still works
4. Remove old `fingerprint_table()` implementation
5. Update `fingerprint_window()` similarly if needed

**Estimated Impact**: 🔥🔥 Medium-High (performance + clarity)

---

### 5. Dev Tooling: Replace with Standard Tools

**Problem**: Homegrown orchestration that ruff + pre-commit already provide.

**Current State**:
- `dev_tools/check_imports.py` - custom git-grep for forbidden modules
- `dev_tools/check_pandas_imports.py` - elaborate block scanner for pandas bans
- `dev_tools/code_quality.py` - mini-orchestrator running ruff, vulture, radon, etc.
- `dev_tools/verify_structure.py` - directory layout assertions

**Complexity Indicators**:
- ~400 LOC of custom tooling
- Import checks don't report which lines fail (just `pass` in loop)
- Worse UX than ruff (which shows file:line:message)
- Reimplementing what ruff can do natively

**Proposal**: Consolidate into ruff config + simple shell script.

**Changes**:
1. **Move import bans to `ruff.toml`**
   - Use `ruff`'s `banned-imports` or `per-file-ignores`
   - Example for pandas ban:
     ```toml
     [tool.ruff.lint.per-file-ignores]
     "src/egregora/**/*.py" = ["pandas"]  # Ban pandas except in TYPE_CHECKING
     ```
   - Delete `check_imports.py` and `check_pandas_imports.py`

2. **Replace `code_quality.py` with `scripts/quality.sh`**
   ```bash
   #!/usr/bin/env bash
   set -e

   echo "Running ruff..."
   uv run ruff check .

   echo "Running tests..."
   uv run pytest --maxfail=1 -q

   echo "Running vulture (optional)..."
   uv run vulture src tests --min-confidence 80 || true

   echo "✅ Quality checks passed"
   ```
   - CI calls `scripts/quality.sh`
   - Humans can call same script
   - Delete `code_quality.py`

3. **Archive `verify_structure.py`**
   - Move to `dev_tools/archive/verify_structure.py`
   - No longer needed after tree stabilized
   - Keep for historical reference if needed

**Benefits**:
- ✅ ~400 LOC removed
- ✅ Better error messages (ruff shows file:line)
- ✅ Standard tooling (easier for contributors)
- ✅ Less to maintain

**Implementation Steps**:
1. Add pandas ban to `ruff.toml` or `pyproject.toml`
2. Test that ruff catches banned imports
3. Create `scripts/quality.sh`
4. Update CI workflow to use `scripts/quality.sh`
5. Delete `check_*.py` and `code_quality.py`
6. Archive `verify_structure.py`

**Estimated Impact**: 🔥🔥 Medium-High (maintenance burden reduction)

---

### 6. Elo Ranking: Extract to Optional Plugin

**Problem**: Experimental feature mixed into core infrastructure.

**Current State**:
- `ELO_RATINGS_SCHEMA` and `ELO_HISTORY_SCHEMA` in core DB schemas
- `database/elo_store.py` - dedicated storage API
- `agents/reader/elo.py` - ranking logic
- Not deeply integrated into core pipeline flows

**Complexity Indicators**:
- Adds tables to core database
- Not clear if Elo is a permanent feature or experiment
- Mixes ranking concern with message processing

**Proposal**: Move to optional plugin structure.

**Changes**:
1. **Create `src/egregora/contrib/elo/`**
   - Move `database/elo_store.py` → `contrib/elo/store.py`
   - Move `agents/reader/elo.py` → `contrib/elo/ranking.py`
   - Move `ELO_RATINGS_SCHEMA`, `ELO_HISTORY_SCHEMA` → `contrib/elo/schemas.py`

2. **Guard tables with feature flag**
   - Tables created only when `ranking.enabled: true` in config
   - Or via explicit `egregora init-elo` command

3. **Update imports**
   - Search for imports from old locations
   - Update to use `egregora.contrib.elo` namespace

4. **Document as optional**
   - Update `docs/` to mark Elo as experimental/optional
   - Clear separation: core platform vs. experiments

**Benefits**:
- ✅ Clearer boundary between core and experiments
- ✅ Core DB schemas leaner
- ✅ Easier to remove if experiment fails
- ✅ Clear signal: "This is optional"

**Implementation Steps**:
1. Create `src/egregora/contrib/elo/` directory
2. Move Elo-related files
3. Update imports across codebase
4. Add feature flag to config schema
5. Update documentation

**Estimated Impact**: 🔥 Low-Medium (organizational clarity)

---

## Implementation Priority

### Phase 1: High-Impact, Low-Risk (Week 1)
1. **P0**: Dev Tooling Simplification (#5)
   - Pure deletion, no behavior change
   - Immediate maintenance win

2. **P0**: Validation Cleanup (#3)
   - Small, focused change
   - Clarifies contracts

3. **P1**: Fingerprinting Optimization (#4)
   - Clear performance win
   - Low risk (existing tests validate checkpointing)

### Phase 2: Structural Changes (Week 2)
4. **P1**: Tracking Unification (#1)
   - Largest LOC reduction
   - Requires careful migration of observability code

5. **P1**: IR Schema Consolidation (#2)
   - Medium risk (tooling change)
   - High value (reduces friction)

### Phase 3: Optional Improvements (Week 3+)
6. **P2**: Elo Plugin Extraction (#6)
   - Low urgency (organizational only)
   - Can defer if time-constrained

## Success Metrics

**Quantitative**:
- [ ] Remove 1,200+ LOC
- [ ] Delete 8+ files
- [ ] Reduce DB tables from 5+ to 2-3 core tables
- [ ] CI runtime reduction (fewer tools to run)

**Qualitative**:
- [ ] New contributors can understand tracking in <10 minutes
- [ ] IR schema changes require updating 1 file (not 3)
- [ ] No "mystery failures" in pre-commit hooks
- [ ] Validation errors are clear (file:line:message)

## Risk Mitigation

**For each change**:
1. ✅ Write tests first (validate current behavior)
2. ✅ Make change incrementally
3. ✅ Run full test suite
4. ✅ Update documentation
5. ✅ Single commit per simplification

**Rollback plan**:
- Each change in separate commit
- Easy to revert individual simplifications
- No breaking changes to pipeline data

**Communication**:
- Update `CLAUDE.md` after each phase
- Document removed features in `CHANGELOG.md`
- Add TENET-BREAK comments where appropriate

## Open Questions

1. **Lineage**: Keep table but stop writing, or remove entirely?
   - **Recommendation**: Add `parent_run_id` column, remove `lineage` table
   - Simpler single-parent model sufficient for current needs

2. **IR JSON lockfile**: Delete or keep for external tools?
   - **Recommendation**: Keep but auto-generate from Python
   - Minimal cost, potentially useful for docs/tooling

3. **Window tracking**: Aggregate metrics in JSON or dedicated columns?
   - **Recommendation**: JSON `attrs` column (more flexible)
   - Can promote to columns later if querying is common

4. **Fingerprinting**: Aggregate stats or timestamp-based?
   - **Recommendation**: Start with aggregate stats (Option A)
   - Migrate to timestamps if even simpler proves sufficient

## Appendix: Complexity Inventory

**Files to Remove** (~8):
- `dev_tools/check_imports.py`
- `dev_tools/check_pandas_imports.py`
- `dev_tools/code_quality.py`
- `dev_tools/verify_structure.py`
- `schema/ir_v1.json` (or auto-generate)
- `scripts/check_ir_schema.py` (replace with generator)

**Files to Simplify** (~6):
- `src/egregora/database/tracking.py` (-200 LOC)
- `src/egregora/database/ir_schema.py` (-100 LOC)
- `src/egregora/database/validation.py` (-50 LOC)
- `src/egregora/utils/fingerprinting.py` (-20 LOC)
- `src/egregora/transformations/windowing.py` (-50 LOC)

**Total Estimated Reduction**: ~1,200 LOC + 8 files

---

## Next Steps

1. **Review & Approve**: Team review of this plan
2. **Create Issues**: One issue per simplification (tracking)
3. **Begin Phase 1**: Start with dev tooling (#5)
4. **Iterate**: Adjust plan based on learnings

**Status**: 🟡 DRAFT - Awaiting approval

---

**Document History**:
- 2025-11-17: Initial draft based on complexity analysis
- 2025-11-17: Added implementation steps and risk mitigation
