# Codebase Cleanup & Organization Plan

**Created**: 2025-01-09
**Status**: Planning
**Goal**: Remove dead code, consolidate redundant files, and organize the codebase to only include code contributing to actual functionality

## Guiding Principles

1. **Single Responsibility**: Each file should have one clear purpose
2. **No Dead Code**: Remove unused imports, functions, and files
3. **DRY (Don't Repeat Yourself)**: Consolidate duplicate code
4. **Clear Structure**: Organize by feature/domain, not by technical layer
5. **Active Use Only**: If it's not imported or called, it should be removed

## Phase 1: Dead Code Analysis (1 day)

### 1.1 Identify Unused Imports
**Action**: Scan all files for unused imports

```bash
# Use ruff to find unused imports
uv run ruff check --select F401 src/
```

**Expected findings**:
- Unused standard library imports
- Imported but never used helper functions
- Star imports that should be explicit

**Deliverable**: List of files with unused imports to clean

### 1.2 Find Unused Functions/Classes
**Action**: Use static analysis to find defined but never called code

```bash
# Use vulture to find dead code
uv run vulture src/egregora/
```

**Expected findings**:
- Helper functions defined but never called
- Classes instantiated nowhere
- Deprecated code paths

**Deliverable**: List of functions/classes to remove or mark for deprecation

### 1.3 Identify Orphaned Files
**Action**: Find Python files that are never imported

**Check**:
- Files in `src/egregora/` not imported anywhere
- Test files without corresponding source files
- Documentation referencing non-existent code

**Deliverable**: List of files to delete or integrate

## Phase 2: Structural Reorganization (2 days)

### 2.1 Consolidate Pipeline Code

**Current structure** (scattered):
```
src/egregora/
├── pipeline.py               # Windowing utilities
├── pipeline/
│   ├── runner.py            # Main pipeline
│   ├── checkpoint.py        # Checkpointing (old)
│   ├── tracking.py          # Run tracking (new)
│   ├── ir.py                # IR validation
│   ├── media_utils.py       # Media processing
│   └── base.py              # PipelineStage protocol
```

**Proposed structure** (consolidated):
```
src/egregora/pipeline/
├── __init__.py              # Re-export create_windows, Window
├── runner.py                # Main pipeline orchestration
├── windowing.py             # create_windows() moved here
├── tracking.py              # Run tracking (keep)
├── validation.py            # IR validation (rename from ir.py)
├── media.py                 # Media processing (rename from media_utils.py)
└── stages/
    ├── __init__.py
    ├── base.py              # PipelineStage protocol
    └── adapters.py          # SourceAdapter protocol
```

**Actions**:
1. Move `create_windows()` from `pipeline.py` → `pipeline/windowing.py`
2. Rename `ir.py` → `validation.py` for clarity
3. Rename `media_utils.py` → `media.py`
4. Move `checkpoint.py` to `pipeline/legacy/` (deprecated)
5. Create `pipeline/stages/` subdirectory for stage protocols

**Deliverable**: Consolidated pipeline structure with clear separation

### 2.2 Consolidate Database Code

**Current structure**:
```
src/egregora/database/
├── schema.py                # Message schemas
├── runs_schema.py           # Runs table schema
├── storage.py               # StorageManager
├── connection.py            # DuckDB connection
├── validation.py            # Schema validation
└── views.py                 # SQL views
```

**Issues**:
- `schema.py` and `runs_schema.py` should be merged
- `connection.py` has minimal code (should merge into storage.py)

**Proposed structure**:
```
src/egregora/database/
├── __init__.py              # Re-exports
├── schemas.py               # All schemas (merge schema.py + runs_schema.py)
├── storage.py               # StorageManager + connection helpers
├── validation.py            # Schema validation (keep)
└── views.py                 # SQL views (keep)
```

**Actions**:
1. Merge `schema.py` + `runs_schema.py` → `schemas.py`
2. Move `connection.py` functions into `storage.py`
3. Update imports across codebase

**Deliverable**: Single source of truth for database schemas

### 2.3 Consolidate Agent Code

**Current structure**:
```
src/egregora/agents/
├── writer/
│   ├── writer_agent.py
│   ├── tools.py
│   ├── context.py
│   └── formatting.py
├── editor/
│   └── editor_agent.py
├── ranking/
│   ├── ranking_agent.py
│   └── elo.py
├── loader.py
├── registry.py
├── resolver.py
└── tools/                   # Shared tools
    ├── rag/
    ├── annotations/
    └── profiler.py
```

**Issues**:
- `loader.py`, `registry.py`, `resolver.py` have overlapping responsibilities
- Not clear which tools are writer-specific vs shared

**Proposed structure**:
```
src/egregora/agents/
├── __init__.py
├── registry.py              # Unified agent registry (merge loader + resolver)
├── writer/
│   ├── agent.py             # Rename from writer_agent.py
│   ├── tools.py             # Writer-specific tools
│   ├── context.py           # Context loading
│   └── formatting.py        # Markdown formatting
├── editor/
│   └── agent.py             # Rename from editor_agent.py
├── ranking/
│   ├── agent.py             # Rename from ranking_agent.py
│   └── elo.py               # Elo algorithm
└── shared/                  # Rename from tools/
    ├── rag/
    ├── annotations/
    └── profiler.py
```

**Actions**:
1. Merge `loader.py` + `resolver.py` → `registry.py`
2. Rename `*_agent.py` → `agent.py` (less redundant)
3. Rename `tools/` → `shared/` for clarity
4. Move writer-specific tools from `shared/` to `writer/tools.py`

**Deliverable**: Clear separation of agent-specific vs shared code

### 2.4 Consolidate Source Adapters

**Current structure**:
```
src/egregora/
├── ingestion/
│   ├── base.py              # InputSource protocol
│   ├── __init__.py          # Re-exports
│   └── slack_input.py       # Slack (placeholder)
├── sources/
│   └── whatsapp/
│       ├── parser.py
│       ├── input.py
│       ├── models.py
│       ├── grammar.py
│       └── pipeline.py
└── adapters.py              # Adapter registry (top-level)
```

**Issues**:
- `ingestion/` and `sources/` have confusing separation
- `adapters.py` at top-level should be in sources/

**Proposed structure**:
```
src/egregora/sources/
├── __init__.py              # Re-export parse_source, adapters
├── registry.py              # Adapter registry (move from top-level)
├── base.py                  # InputSource + SourceAdapter protocols
├── whatsapp/
│   ├── parser.py
│   ├── models.py
│   ├── grammar.py
│   └── adapter.py           # WhatsApp adapter
└── slack/
    └── adapter.py           # Slack adapter (placeholder)
```

**Actions**:
1. Delete `ingestion/` directory (move protocols to `sources/base.py`)
2. Move `adapters.py` → `sources/registry.py`
3. Consolidate WhatsApp code into single `sources/whatsapp/` structure
4. Update all imports to use `from egregora.sources import ...`

**Deliverable**: Single `sources/` directory for all input adapters

## Phase 3: Remove Deprecated Code (1 day)

### 3.1 Remove Old Checkpoint System

**Files to remove**:
- `src/egregora/pipeline/checkpoint.py` (replaced by tracking.py)
- All references to JSON-based checkpoint files

**Actions**:
1. Move `checkpoint.py` to `pipeline/legacy/` (mark deprecated)
2. Add deprecation warnings
3. Update documentation to reference new tracking system
4. Remove from imports

**Deliverable**: Old checkpoint system archived or deleted

### 3.2 Remove Duplicate Utilities

**Scan for**:
- Duplicate date/time utilities
- Duplicate string formatting helpers
- Duplicate path manipulation functions

**Actions**:
1. Consolidate into `src/egregora/utils/`
2. Remove duplicates
3. Update imports

**Deliverable**: Single source for each utility function

### 3.3 Remove Unused Config Options

**Check**:
- Config fields defined but never read
- Environment variables defined but never used
- CLI flags that don't affect behavior

**Actions**:
1. Audit `config/types.py` for unused fields
2. Remove dead config options
3. Update documentation

**Deliverable**: Minimal config surface area

## Phase 4: Test Cleanup (1 day)

### 4.1 Remove Orphaned Tests

**Scan for**:
- Test files testing deleted code
- Duplicate test cases
- Tests that always pass (no assertions)

**Actions**:
1. Map tests to source files
2. Delete tests for removed code
3. Consolidate duplicate tests

**Deliverable**: Every test corresponds to active code

### 4.2 Organize Test Structure

**Current structure**:
```
tests/
├── unit/
├── integration/
├── e2e/
├── agents/
├── evals/
├── linting/
└── fixtures/
```

**Proposed structure** (mirror source):
```
tests/
├── unit/
│   ├── pipeline/
│   ├── database/
│   ├── sources/
│   ├── agents/
│   └── utils/
├── integration/
│   ├── end_to_end.py
│   └── api_tests.py
└── fixtures/
    ├── data/
    └── golden/
```

**Actions**:
1. Reorganize tests to mirror `src/` structure
2. Move `evals/` into `integration/`
3. Move `linting/` checks to pre-commit hooks
4. Consolidate fixtures

**Deliverable**: Tests organized by feature, not by test type

## Phase 5: Documentation Cleanup (1 day)

### 5.1 Remove Outdated Documentation

**Scan for**:
- Documentation referencing deleted code
- Examples using deprecated APIs
- Dead links

**Actions**:
1. Audit `docs/` directory
2. Remove references to removed code
3. Update examples to use current APIs

**Deliverable**: All documentation references active code

### 5.2 Consolidate Guides

**Current documentation**:
- Multiple getting started guides
- Duplicate API references
- Scattered architecture notes

**Proposed structure**:
```
docs/
├── index.md                 # Single getting started
├── guides/
│   ├── quickstart.md
│   ├── configuration.md
│   └── deployment.md
├── architecture/
│   ├── pipeline.md
│   ├── agents.md
│   └── sources.md
├── api/
│   ├── database.md
│   ├── agents.md
│   └── sources.md
└── observability/
    └── runs-tracking.md
```

**Actions**:
1. Merge duplicate guides
2. Create clear hierarchy
3. Remove redundancy

**Deliverable**: Single source of truth for each topic

## Phase 6: Code Quality Improvements (2 days)

### 6.1 Enforce Consistent Naming

**Issues**:
- Mixed `snake_case` and `camelCase`
- Inconsistent file naming (`writer_agent.py` vs `storage.py`)
- Unclear abbreviations

**Actions**:
1. Rename files for consistency (see Phase 2)
2. Use full words instead of abbreviations
3. Follow Python naming conventions strictly

**Deliverable**: Consistent naming throughout codebase

### 6.2 Consolidate Error Handling

**Issues**:
- Mix of `raise` and `return None`
- Inconsistent error messages
- Some errors swallowed silently

**Actions**:
1. Define custom exception hierarchy
2. Standardize error handling patterns
3. Remove silent error swallowing

**Deliverable**: Consistent error handling

### 6.3 Remove TODO Comments

**Scan for**:
- `# TODO:` comments for completed work
- Outdated `FIXME` notes
- `HACK` comments that should be proper solutions

**Actions**:
1. Convert TODOs to GitHub issues
2. Fix or document HACKs
3. Remove completed TODOs

**Deliverable**: No stale TODO comments

## Phase 7: Final Validation (1 day)

### 7.1 Run Full Test Suite

**Actions**:
1. Run all tests after each phase
2. Ensure 100% pass rate
3. Check coverage hasn't decreased

**Deliverable**: All tests passing

### 7.2 Performance Regression Check

**Actions**:
1. Benchmark pipeline performance
2. Ensure no significant slowdowns
3. Verify memory usage unchanged

**Deliverable**: No performance regressions

### 7.3 Update CLAUDE.md

**Actions**:
1. Update all code structure references
2. Update common command examples
3. Update architecture diagrams

**Deliverable**: CLAUDE.md reflects new structure

## Expected Outcomes

### Metrics

**Before cleanup** (estimated):
- Total files: ~150
- Lines of code: ~15,000
- Unused imports: ~50+
- Dead functions: ~20+
- Orphaned files: ~10+

**After cleanup** (target):
- Total files: ~100 (-33%)
- Lines of code: ~10,000 (-33%)
- Unused imports: 0
- Dead functions: 0
- Orphaned files: 0

### Benefits

1. **Easier onboarding** - New contributors can understand structure faster
2. **Faster development** - Less code to navigate means faster changes
3. **Fewer bugs** - Dead code can't have bugs
4. **Better performance** - Smaller import graph means faster startup
5. **Clearer purpose** - Every file has clear responsibility

## Timeline

**Total effort**: 9 days (~ 2 weeks)

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Dead Code Analysis | 1 day | None |
| Phase 2: Structural Reorganization | 2 days | Phase 1 |
| Phase 3: Remove Deprecated Code | 1 day | Phase 2 |
| Phase 4: Test Cleanup | 1 day | Phase 3 |
| Phase 5: Documentation Cleanup | 1 day | Phase 4 |
| Phase 6: Code Quality Improvements | 2 days | Phase 5 |
| Phase 7: Final Validation | 1 day | Phase 6 |

## Risks & Mitigation

### Risk: Breaking Changes

**Mitigation**:
- Run tests after each file change
- Use `git bisect` if issues arise
- Keep cleanup commits small and focused

### Risk: Merge Conflicts

**Mitigation**:
- Work in feature branch
- Merge main frequently
- Use atomic commits

### Risk: Lost Functionality

**Mitigation**:
- Document removed code
- Keep backup branch
- Add deprecation warnings before removal

## Success Criteria

- [ ] Zero unused imports (verified by ruff)
- [ ] Zero dead code (verified by vulture)
- [ ] All tests passing (100% pass rate)
- [ ] Documentation up to date (all references valid)
- [ ] Consistent naming (manual review)
- [ ] Clear file organization (manual review)
- [ ] No TODO comments for completed work
- [ ] CLAUDE.md updated with new structure

## Next Steps

1. **Approval** - Review plan with stakeholders
2. **Branching** - Create `cleanup/structural-refactor` branch
3. **Phase 1** - Start with dead code analysis
4. **Incremental commits** - Commit after each sub-phase
5. **Continuous testing** - Run tests after every change
6. **PR review** - Submit PR after Phase 7 completion
