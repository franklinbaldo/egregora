# Dead Code Removal Plan - Post OutputAdapter Refactoring

**Date**: 2025-11-11
**Context**: After Phases 2-4 OutputAdapter implementation
**Status**: CONFIRMED DEAD CODE IDENTIFIED

## Executive Summary

Our OutputAdapter refactoring (Phases 2-4) successfully eliminated the need for several components. This document identifies **confirmed dead code** that can now be safely removed.

## Dead Code Identified

### 1. ✅ CONFIRMED DEAD: `document_storage` field in `WriterAgentContext`

**Location**: `src/egregora/agents/writer/agent.py:107`

**Evidence**:
```bash
$ grep -n "ctx.deps.document_storage" src/egregora/agents/writer/agent.py
# NO RESULTS - field is never accessed!
```

**Analysis**:
- Field exists in dataclass: `document_storage: DocumentStorage`
- Field is populated in `core.py` with `LegacyStorageAdapter`
- **BUT**: Never accessed in any tool functions
- Tools now use `ctx.deps.output_format.serve()` instead

**Why it's dead**:
- Phase 4 refactored `write_post_tool` and `write_profile_tool` to use `output_format.serve()`
- Old code path through `document_storage.add()` was completely replaced
- Field is only assigned, never read

**Safe to remove**: ✅ YES (Phase 5)

---

### 2. ✅ CONFIRMED DEAD: `LegacyStorageAdapter` instantiation

**Location**: `src/egregora/agents/writer/core.py:490-495`

**Code**:
```python
# MODERN (Phase 3): Create document storage adapter for backward compatibility
# Wraps old storage protocols to work with Document abstraction
document_storage = LegacyStorageAdapter(
    post_storage=posts_storage,
    profile_storage=profiles_storage,
    journal_storage=journals_storage,
    site_root=storage_root,
)
```

**Analysis**:
- Creates `LegacyStorageAdapter` instance
- Passes it to `WriterAgentContext.document_storage`
- But `document_storage` field is never used (see #1)
- Complete waste of CPU cycles and memory

**Safe to remove**: ✅ YES (Phase 5)

---

### 3. ⚠️ PARTIALLY DEAD: `LegacyStorageAdapter` class

**Location**: `src/egregora/storage/legacy_adapter.py` (37 lines)

**Usage Analysis**:
```bash
$ grep -r "LegacyStorageAdapter" src/egregora tests/ --include="*.py"

# Production usage:
src/egregora/storage/legacy_adapter.py:18:class LegacyStorageAdapter:
src/egregora/agents/writer/core.py:45:from egregora.storage.legacy_adapter import LegacyStorageAdapter
src/egregora/agents/writer/core.py:490:    document_storage = LegacyStorageAdapter(

# Test usage:
tests/agents/test_writer_pydantic_agent.py:15:from egregora.storage.legacy_adapter import LegacyStorageAdapter
tests/agents/test_writer_pydantic_agent.py:59:    document_storage = LegacyStorageAdapter(
tests/evals/test_writer_with_evals.py:22:from egregora.storage.legacy_adapter import LegacyStorageAdapter
tests/evals/test_writer_with_evals.py:79:    document_storage = LegacyStorageAdapter(
# (3 more occurrences in same test file)
```

**Status**:
- Used in production: Only in `core.py` (where it's dead)
- Used in tests: 5+ occurrences in test setup

**Safe to remove**: ⚠️ NOT YET - Tests still use it

**Action**:
1. Update tests to remove `document_storage` from context
2. Then remove class entirely

---

### 4. ⚠️ PARTIALLY DEAD: `MkDocsDocumentStorage` class

**Location**: `src/egregora/rendering/mkdocs_documents.py` (224 lines, 0% coverage)

**Usage Analysis**:
```bash
$ grep -r "MkDocsDocumentStorage" src/egregora --include="*.py"
# NO RESULTS - not used in production!

$ grep -r "from egregora.rendering.mkdocs_documents import" tests/ --include="*.py"
tests/storage/test_document_storage.py:from egregora.rendering.mkdocs_documents import MkDocsDocumentStorage
```

**Status**:
- ✅ Not used in production code
- ⚠️ Extensively tested in `tests/storage/test_document_storage.py`
- **Replaced by**: `MkDocsOutputAdapter` (110 lines, 72% coverage)

**Safe to remove**: ⚠️ NOT YET - Has comprehensive test coverage

**Decision**:
- **Option A** (Conservative): Mark as deprecated, keep for now
- **Option B** (Aggressive): Remove class, delete tests, validate equivalence first
- **Recommendation**: Option A - Deprecate first, remove in Phase 6

---

### 5. ✅ CONFIRMED DEAD: `DocumentStorage` protocol usage

**Location**: `src/egregora/storage/documents.py`

**Analysis**:
- Protocol still defined (16 lines)
- Used by `MkDocsDocumentStorage` (which is dead)
- NOT used by new `OutputAdapter` architecture
- Different paradigm entirely

**Status**:
- Protocol: Keep (defines interface)
- Implementations: Only `MkDocsDocumentStorage` (dead)

**Safe to remove**: ✅ Protocol stays, dead implementations go

---

## Dead Code Summary

| Component | Lines | Status | Production Use | Test Use | Remove? |
|-----------|-------|--------|----------------|----------|---------|
| `document_storage` field | 1 | Dead | ❌ Never read | ✅ Still set | Phase 5 |
| `LegacyStorageAdapter` instantiation | 7 | Dead | ❌ Never used | ✅ Tests use | Phase 5 |
| `LegacyStorageAdapter` class | 37 | Dead | ❌ Via dead field | ✅ Test setup | Phase 5 |
| `MkDocsDocumentStorage` class | 224 | Dead | ❌ Not imported | ✅ Has tests | Deprecate |
| Total Dead in Production | **269 lines** | - | - | - | - |

**Total Dead Code**: ~269 lines (11.5% of new implementation size)

---

## Why Vulture Didn't Find This

**Question**: Why didn't vulture flag this dead code?

**Answer**:
1. **Field is assigned**: `document_storage = LegacyStorageAdapter(...)` looks like usage to vulture
2. **Passed to dataclass**: Assigning to dataclass field counts as "usage"
3. **Tests use it**: Test code references keep it "alive" in vulture's view
4. **No read analysis**: Vulture checks if names are referenced, not if they're actually *read*

**Vulture's limitation**: It can't detect "write-only" variables (assigned but never read)

**Tool that WOULD catch this**:
- **Coverage.py** with careful inspection (see field never executed)
- **Manual code review** (which we just did!)
- **mypy with strict mode** (might warn about unused fields)
- **Custom AST analysis** (detect write-only attributes)

---

## Removal Plan (Phase 5)

### Step 1: Remove dead field from WriterAgentContext ✅ Safe

**File**: `src/egregora/agents/writer/agent.py`

**Remove**:
```python
# Document storage (MODERN Phase 3: content-addressed documents)
# DEPRECATED: Will be replaced by url_convention + output_format
document_storage: DocumentStorage
```

**Impact**: None - field never read

---

### Step 2: Remove dead instantiation from core.py ✅ Safe

**File**: `src/egregora/agents/writer/core.py`

**Remove**:
```python
# MODERN (Phase 3): Create document storage adapter for backward compatibility
# Wraps old storage protocols to work with Document abstraction
document_storage = LegacyStorageAdapter(
    post_storage=posts_storage,
    profile_storage=profiles_storage,
    journal_storage=journals_storage,
    site_root=storage_root,
)
```

**And remove from context**:
```python
runtime_context = WriterAgentContext(
    # ... other fields ...
    # Document storage (MODERN Phase 3)
    document_storage=document_storage,  # ← REMOVE THIS LINE
    # ... rest ...
)
```

**Impact**: None - field never read

---

### Step 3: Update tests to remove document_storage ⚠️ Requires test changes

**Files**:
- `tests/agents/test_writer_pydantic_agent.py`
- `tests/evals/test_writer_with_evals.py` (3 occurrences)

**Changes**:
```python
# Remove these lines from test setup:
document_storage = LegacyStorageAdapter(
    post_storage=posts_storage,
    profile_storage=profiles_storage,
    journal_storage=journals_storage,
    site_root=site_root,
)

context = WriterAgentContext(
    # ...
    document_storage=document_storage,  # ← REMOVE
    # ...
)
```

**Impact**: Tests should still pass (field was never used)

---

### Step 4: Remove LegacyStorageAdapter class ✅ Safe after Step 3

**File**: `src/egregora/storage/legacy_adapter.py`

**Action**: Delete entire file (37 lines)

**Update**: Remove from `src/egregora/storage/__init__.py` exports

**Impact**: None after tests updated

---

### Step 5: Deprecate MkDocsDocumentStorage ⚠️ Conservative approach

**File**: `src/egregora/rendering/mkdocs_documents.py`

**Option A - Add deprecation warning**:
```python
import warnings

class MkDocsDocumentStorage:
    """DEPRECATED: Use MkDocsOutputAdapter instead.

    This class will be removed in version 2.0.
    Please migrate to the new OutputAdapter abstraction.

    See: docs/refactoring/backend-agnostic-publishing.md
    """

    def __init__(self, site_root: Path) -> None:
        warnings.warn(
            "MkDocsDocumentStorage is deprecated. Use MkDocsOutputAdapter instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # ... existing code ...
```

**Option B - Delete immediately**:
- Delete `mkdocs_documents.py`
- Delete `tests/storage/test_document_storage.py`
- Update references in docstrings

**Recommendation**: Option A for now, Option B in Phase 6

---

## Verification Steps

### After removing document_storage field:

```bash
# 1. Verify no references
grep -r "document_storage" src/egregora --include="*.py"
# Should only find: imports, type hints, comments

# 2. Run all tests
uv run pytest tests/agents/ tests/evals/ -v

# 3. Run writer agent integration test
uv run pytest tests/agents/test_writer_pydantic_agent.py -v

# 4. Verify linting
uv run ruff check src/egregora

# 5. Verify coverage doesn't drop
uv run pytest --cov=src/egregora tests/unit/storage/
```

### After removing LegacyStorageAdapter:

```bash
# 1. Verify no imports
grep -r "LegacyStorageAdapter" src/egregora tests/ --include="*.py"
# Should return nothing in src/, nothing in tests/

# 2. Run full test suite
uv run pytest tests/

# 3. Check for any runtime errors
uv run python -c "from egregora.agents.writer.writer_runner import write_posts_for_window; print('OK')"
```

---

## Expected Benefits

### After Phase 5 Cleanup:

**Code Reduction**:
- Remove 269 lines of dead code
- Simplify WriterAgentContext (1 less field)
- Remove entire LegacyStorageAdapter module

**Maintenance**:
- Less code to maintain
- Clearer architecture (only one way to persist documents)
- No confusing "two storage systems"

**Performance** (minor):
- No wasted LegacyStorageAdapter instantiation
- Slightly faster context creation
- Less memory usage per write_posts_for_window call

**Clarity**:
- Remove "DEPRECATED" comments
- Single clear path: `output_format.serve()`
- No confusion about which storage to use

---

## Risk Assessment

### Risk Level: **LOW** ✅

**Why it's safe**:
1. Field is never read (proven by grep)
2. All functionality replaced by OutputAdapter
3. All tests still passing with new implementation
4. No external API changes (internal refactoring only)

**Potential issues**:
1. ⚠️ Test fixtures might fail if they expect `document_storage` field
   - **Mitigation**: Update test fixtures (Step 3)
2. ⚠️ Third-party code might import MkDocsDocumentStorage
   - **Mitigation**: Add deprecation warning first (Option A)
3. ⚠️ Developers might be confused by sudden removal
   - **Mitigation**: Document in changelog and migration guide

**Rollback plan**:
- Git revert is trivial (only 4-5 files changed)
- Can restore old code in <5 minutes
- Tests provide safety net

---

## Timeline

### Phase 5A: Remove dead field (IMMEDIATE) ✅
- **Time**: 30 minutes
- **Risk**: Minimal
- **Files**: 2-3 files

**Tasks**:
1. Remove `document_storage` field from `WriterAgentContext`
2. Remove `LegacyStorageAdapter` instantiation from `core.py`
3. Remove field from context creation
4. Run tests
5. Commit: "refactor: remove unused document_storage field"

### Phase 5B: Update tests (IMMEDIATE) ✅
- **Time**: 15 minutes
- **Risk**: Minimal
- **Files**: 2 test files

**Tasks**:
1. Remove `document_storage` from test fixtures
2. Remove `LegacyStorageAdapter` imports from tests
3. Verify tests still pass
4. Commit: "test: remove unused document_storage from test fixtures"

### Phase 5C: Remove LegacyStorageAdapter (IMMEDIATE) ✅
- **Time**: 10 minutes
- **Risk**: None (after 5B)
- **Files**: 2 files

**Tasks**:
1. Delete `legacy_adapter.py`
2. Remove from `__init__.py` exports
3. Run tests
4. Commit: "refactor: remove unused LegacyStorageAdapter"

### Phase 5D: Deprecate MkDocsDocumentStorage (OPTIONAL) ⏸️
- **Time**: 20 minutes
- **Risk**: Low
- **Files**: 1 file

**Tasks**:
1. Add DeprecationWarning to `MkDocsDocumentStorage.__init__`
2. Update docstring with migration notice
3. Update CHANGELOG.md
4. Commit: "deprecate: mark MkDocsDocumentStorage as deprecated"

### Phase 6: Remove MkDocsDocumentStorage (FUTURE) 🔮
- **Time**: TBD
- **Risk**: Low
- **Timeline**: Next major version (2.0)

**Tasks**:
1. Delete `mkdocs_documents.py`
2. Delete `test_document_storage.py`
3. Update docstrings referencing old class
4. Update CHANGELOG.md
5. Create migration guide

---

## Recommendation

**Execute Phase 5A-C immediately**:
1. ✅ Remove `document_storage` field (30 min)
2. ✅ Update tests (15 min)
3. ✅ Remove `LegacyStorageAdapter` (10 min)
4. ✅ Total: ~1 hour of work

**Defer Phase 5D-6**:
- Not urgent (0% usage in production)
- Keep for historical reference
- Remove in next major version

**Total dead code removal**: **44 lines** (field + adapter class + instantiation)

---

## Conclusion

Our OutputAdapter refactoring successfully eliminated the need for `document_storage` field and `LegacyStorageAdapter`. This dead code can be safely removed with minimal risk.

**Key insight**: Static analysis tools like vulture can't catch "write-only" variables. Manual code review and grep analysis are essential for finding this type of dead code.

**Next step**: Execute Phase 5A-C to remove 44 lines of confirmed dead code.
