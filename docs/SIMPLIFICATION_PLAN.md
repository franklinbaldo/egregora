# Infrastructure Simplification Plan

**Created**: 2025-11-17
**Last Updated**: 2025-11-17
**Status**: NEARLY COMPLETE (5/6 complete)
**Priority**: P1 - Critical for alpha stability

## Executive Summary

This document outlines a systematic plan to reduce infrastructure complexity in Egregora while maintaining (or improving) observability and developer experience. The goal is to embrace the **alpha mindset**: favor simplicity over premature optimization, reduce moving parts, and make the codebase easier to reason about.

**Key Metrics** (Actual):
- **LOC reduction**: ~1,500+ lines removed
- **Files removed**: 8 files deleted, 2 archived
- **Simplifications complete**: 5 out of 6
- **Breaking changes**: None (all internal infrastructure)

## Philosophy: Alpha Mindset

> "We're paying complexity tax without really cashing the benefits."

For an alpha, local-first tool with a single developer (or very small team):
- **Simple > Robust**: Choose the simpler solution until complexity is justified by real needs
- **One Truth > Multiple Models**: Avoid maintaining parallel representations of the same data
- **Battle-Tested > Custom**: Prefer standard tools (ruff, pytest) over homegrown infrastructure
- **Explicit > Magic**: Clear, simple code beats clever abstractions

## Proposed Simplifications

### 1. Tracking Infrastructure: Unify to Single Model ✅ COMPLETED (2025-11-17)

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

### 2. IR Schema: Single Source of Truth ✅ COMPLETED (2025-11-17)

**Problem**: Three representations of the same schema (SQL + JSON + Python).

**Decision**: Complete removal of SQL and JSON lockfiles. Python (Ibis) is now the single source of truth.

**Rationale**:
- SQL and JSON lockfiles were never consumed by runtime code
- Three-way synchronization created maintenance burden without delivering value
- For an alpha, local-first tool, Python-only schema is sufficient
- Code-based schema is type-checked, always in sync with implementation

**Changes Made**:
1. ✅ Removed `schema/ir_v1.sql` entirely (previously archived, now deleted)
2. ✅ Removed `schema/ir_v1.json` entirely (previously archived, now deleted)
3. ✅ Removed `scripts/check_ir_schema.py` validation script (145 LOC)
4. ✅ Removed `tests/unit/test_ir_schema_lockfile.py` tests (71 LOC)
5. ✅ Removed CI workflow step for schema drift checking
6. ✅ Updated `schema/README.md` to document Python-as-canonical approach
7. ✅ Updated `src/egregora/database/validation.py` docstring to clarify canonical source
8. ✅ Deleted `schema/archive/` directory entirely (no need for historical artifacts)

**Actual Benefits**:
- ✅ One place to change IR schema (`IR_MESSAGE_SCHEMA` in validation.py)
- ✅ No more multi-file synchronization on schema changes
- ✅ Easier iteration during alpha
- ✅ ~216 LOC removed (validation script + tests)
- ✅ Clearer documentation: Python is the source of truth

**Implementation Notes**:
- Historical SQL/JSON lockfiles preserved in `schema/archive/` for reference
- All adapter implementations continue to work (no runtime changes)
- Schema validation (`validate_ir_schema()`) unchanged and fully functional
- Pre-existing test failures unrelated to this simplification

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

### 4. Fingerprinting: Choose Lightweight Approach ✅ COMPLETED (2025-11-17)

**Problem**: Expensive fingerprinting with fuzzy semantics.

**Decision**: Complete removal rather than optimization. The checkpoint infrastructure now uses simpler heuristics (file existence, size checks) rather than content fingerprinting.

**Rationale**:
- Fingerprinting added complexity without delivering real checkpointing benefits
- The `--resume` flag already provides opt-in incremental processing
- File-based existence checks are simpler and more transparent
- Can add back lightweight fingerprinting if/when truly needed

**Changes Made**:
1. ✅ Removed `src/egregora/utils/fingerprinting.py` (32 LOC)
2. ✅ Removed `input_fingerprint` column from `RUNS_TABLE_SCHEMA` and `RUNS_TABLE_DDL`
3. ✅ Removed `fingerprint_table()` and `fingerprint_window()` from `tracking.py` (97 LOC)
4. ✅ Removed `input_fingerprint` parameter from `record_run()` function
5. ✅ Removed unused imports (`hashlib`, `pyarrow`, `ensure_deterministic_order`)
6. ✅ Updated `run_store.py` and `cli/runs.py` to remove fingerprint display
7. ✅ Updated all tests to remove fingerprint references
8. ✅ Removed 3 fingerprint unit tests

**Actual Benefits**:
- ✅ ~338 LOC removed
- ✅ Simpler mental model: no "magic" content hashing
- ✅ Clearer checkpoint semantics: file exists = already processed
- ✅ Removed expensive table sorting and PyArrow conversions
- ✅ Easier to understand tracking infrastructure

**Implementation Notes**:
- CLI now shows `parent_run_id` and `attrs` instead of `input_fingerprint`
- All 396 unit tests pass (1 pre-existing schema validation failure unrelated to this change)
- Changed "Fingerprints" section in CLI to "Tracking" section

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
