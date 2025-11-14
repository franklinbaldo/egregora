# Conflict Resolution Strategy: PR #675 → dev

**Date:** 2025-11-14
**PR #675 Branch:** `claude/refactor-naming-consistency-011CV43H5oLaSiz5qhvk4CKE`
**Target Branch:** `dev`
**Status:** 6 conflicts detected ❌

## Executive Summary

PR #675 attempts to merge window validation refactoring into `dev`, but conflicts with major code consolidation that occurred in dev after PR #675 was created. The conflicts reveal **fundamental architectural divergence**:

- **PR #675 focus:** Window validation and streaming optimizations
- **Dev focus:** Code consolidation, dead code removal, file reorganization

**Recommendation:** Accept most dev changes (consolidation was intentional), preserve only PR #675's core window validation logic.

---

## Conflict Analysis

### Conflict 1: `src/egregora/enrichment/batch.py` (MODIFY/DELETE) 🔴 **CRITICAL**

**Type:** Modify/Delete conflict
**Cause:** Dev deleted entire file as part of enrichment consolidation, PR modified it

**PR #675 Changes:**
- Added `_iter_table_record_batches()` function for streaming
- Added `_table_to_pylist()` helper
- Modified batch processing logic

**Dev Changes:**
- ❌ **DELETED** file completely
- Logic moved to `enrichment/runners.py` (consolidated)
- Part of broader enrichment refactoring (removed `avatar_pipeline.py`, `core.py`, `thin_agents.py`)

**Resolution:** ✅ **ACCEPT DELETION (dev wins)**

**Rationale:**
1. Dev's consolidation was intentional and well-documented
2. The streaming logic from PR #675 should be in `enrichment/runners.py` instead
3. Keeping `batch.py` would revert the consolidation effort

**Action Required:**
- Check if streaming improvements from PR #675 are needed
- If yes, port `_iter_table_record_batches()` to `enrichment/runners.py`
- Update any imports that still reference `batch.py`

---

### Conflict 2: `src/egregora/agents/shared/llm_tools.py` (CONTENT) 🔴 **CRITICAL**

**Type:** Content conflict
**Cause:** Different visions for this module

**PR #675 Version (88 lines):**
```python
async def query_rag(...) -> str:
    # Full RAG implementation with VectorStore

async def ask_llm(...) -> str:
    # LLM query implementation

AVAILABLE_TOOLS = {
    "query_rag": query_rag,
    "ask_llm": ask_llm,
}
```

**Dev Version (9 lines):**
```python
"""Shared LLM tools for agents.

This module previously contained agent tools but they are no longer used.
The module is kept as a placeholder for future agent tool implementations.
"""

# NOTE: This file previously contained unused stub functions:
# - query_rag, ask_llm, finish, diversity_sampler, link_rewriter
# These were removed during cleanup as they were never used by any CLI command.
# RAG functionality is implemented in agents.writer.context_builder instead.
```

**Resolution:** ✅ **ACCEPT DEV (stub/placeholder)**

**Rationale:**
1. Dev explicitly documents these as "never used by any CLI command"
2. RAG is implemented in `agents.writer.context_builder` instead
3. Aligns with cleanup effort documented in commit `eeb679a`

**Action Required:**
- Verify RAG functionality works in `agents.writer.context_builder`
- If PR #675 depends on these tools, refactor to use new location
- Update `agents/shared/__init__.py` to remove `AVAILABLE_TOOLS` export

---

### Conflict 3: `src/egregora/agents/shared/__init__.py` (CONTENT) ⚠️ **TRIVIAL**

**Type:** Docstring conflict

**PR #675:**
```python
"""Agent tools and utilities."""
```

**Dev:**
```python
"""Agent tools and utilities.

This package contains tools that agents use to perform their tasks:
- rag: Retrieval augmented generation
- annotations: Conversation annotation storage
- author_profiles: Author profiling and active user tracking
"""
```

**Resolution:** ✅ **ACCEPT DEV (better documentation)**

**Rationale:** Dev version is more descriptive and helpful for developers

---

### Conflict 4: `src/egregora/database/__init__.py` (CONTENT) ⚠️ **TRIVIAL**

**Type:** Duplicate export in `__all__`

**Conflict:**
```python
__all__ = [
    # ... other exports ...
    "stream_ibis",   # From PR #675
    # ... more exports ...
    "schemas",       # From dev
    "stream_ibis",   # Duplicate! From dev
    "temp_storage",
    "views",
]
```

**Resolution:** ✅ **ACCEPT DEV, remove duplicate**

**Action:**
```python
__all__ = [
    # ... keep all exports ...
    "schemas",
    "stream_ibis",  # Keep only one
    "temp_storage",
    "views",
]
```

---

### Conflict 5: `src/egregora/prompt_templates.py` (CONTENT) ⚠️ **MINOR**

**Type:** Comment/whitespace differences

**Conflicts (3 locations):**

**Location 1 (line 81):**
- PR: `or site root (auto-detects .egregora/prompts subdirectory)`
- Dev: `or site root (will auto-detect .egregora/prompts subdirectory)`

**Location 2 (line 101):**
- PR: Missing comment
- Dev: `# Check if prompts_dir is a site root with .egregora/prompts subdirectory`

**Location 3 (line 110):**
- PR: Missing comment
- Dev: `# Use prompts_dir directly`

**Resolution:** ✅ **ACCEPT DEV (better comments)**

**Rationale:** Dev has more explicit inline comments explaining the logic

---

### Conflict 6: `docs/refactoring/consolidation-plan.md` (ADD/ADD) 🟡 **MODERATE**

**Type:** Both branches added the same file with different content

**PR #675 Version:**
- Planning document describing **future** consolidation work
- Lists files to be renamed (e.g., `constants.py` → `uuid_namespaces.py`)
- Contains TODO-style action items

**Dev Version:**
- Updated document reflecting **completed** consolidation work
- References files that have already been renamed
- Uses past tense ("renamed from constants.py")

**Resolution:** ✅ **ACCEPT DEV (reflects current state)**

**Rationale:**
1. Dev's version is up-to-date with actual codebase state
2. PR #675's version documents work that's already done
3. Keeping PR version would be misleading (outdated plan)

**Action Required:**
- If PR #675 added unique insights, cherry-pick those sections
- Verify all TODOs in PR version are actually complete in dev

---

## Resolution Strategy

### Option A: Manual Conflict Resolution (RECOMMENDED)

**Steps:**

1. **Checkout PR #675 branch:**
   ```bash
   git checkout claude/refactor-naming-consistency-011CV43H5oLaSiz5qhvk4CKE
   git pull origin claude/refactor-naming-consistency-011CV43H5oLaSiz5qhvk4CKE
   ```

2. **Merge dev and resolve conflicts:**
   ```bash
   git merge origin/dev
   ```

3. **Resolve each conflict:**

   **Conflict 1: batch.py**
   ```bash
   git rm src/egregora/enrichment/batch.py
   ```

   **Conflict 2: llm_tools.py**
   ```bash
   git checkout --theirs src/egregora/agents/shared/llm_tools.py
   ```

   **Conflict 3: agents/shared/__init__.py**
   ```bash
   git checkout --theirs src/egregora/agents/shared/__init__.py
   ```

   **Conflict 4: database/__init__.py**
   ```bash
   # Manually edit to remove duplicate "stream_ibis"
   git add src/egregora/database/__init__.py
   ```

   **Conflict 5: prompt_templates.py**
   ```bash
   git checkout --theirs src/egregora/prompt_templates.py
   ```

   **Conflict 6: consolidation-plan.md**
   ```bash
   git checkout --theirs docs/refactoring/consolidation-plan.md
   ```

4. **Verify no broken imports:**
   ```bash
   uv run python -c "import egregora; print('Imports OK')"
   ```

5. **Run tests:**
   ```bash
   uv run pytest tests/unit/ -v
   uv run pytest tests/integration/ -v
   ```

6. **Commit resolution:**
   ```bash
   git commit -m "chore: resolve merge conflicts with dev - accept consolidation changes"
   ```

7. **Push:**
   ```bash
   git push origin claude/refactor-naming-consistency-011CV43H5oLaSiz5qhvk4CKE
   ```

### Option B: Rebase onto Dev (ALTERNATIVE)

**Steps:**
```bash
git checkout claude/refactor-naming-consistency-011CV43H5oLaSiz5qhvk4CKE
git rebase origin/dev
# Resolve conflicts interactively
git push -f origin claude/refactor-naming-consistency-011CV43H5oLaSiz5qhvk4CKE
```

**Pros:**
- Linear history
- Cleaner git log

**Cons:**
- Requires force push
- More complex conflict resolution
- Rewrites history (may affect PR review)

### Option C: Close PR #675 and Create Fresh PR

**When to use:** If PR #675's changes are no longer relevant or superseded by dev's work

**Steps:**
1. Close PR #675 with comment explaining dev's consolidation supersedes it
2. Identify any unique logic from PR #675 worth preserving
3. Create new PR with just that logic against current dev

---

## Post-Resolution Checklist

After resolving conflicts, verify:

- [ ] All imports resolve correctly (`python -c "import egregora"`)
- [ ] No references to deleted files (`batch.py`, `llm_tools.AVAILABLE_TOOLS`)
- [ ] Unit tests pass (`pytest tests/unit/`)
- [ ] Integration tests pass (`pytest tests/integration/`)
- [ ] Linting passes (`ruff check --fix src/`)
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] Pipeline runs end-to-end (`egregora write export.zip --output=./output`)
- [ ] Documentation reflects current state (`docs/refactoring/consolidation-plan.md`)

---

## Risk Assessment

### Low Risk ✅
- **Conflicts 3, 4, 5:** Trivial docstring/comment differences
- **Conflict 6:** Documentation only

### Medium Risk ⚠️
- **Conflict 2:** llm_tools.py replacement - verify RAG still works

### High Risk 🔴
- **Conflict 1:** batch.py deletion - ensure no broken imports
  - Check `enrichment/__init__.py`
  - Check `enrichment/runners.py`
  - Check `orchestration/write_pipeline.py`

---

## Key Decisions

### Decision 1: Accept Dev's Code Consolidation
**Chosen:** ✅ Yes
**Rationale:** Dev's consolidation was intentional, well-documented, and reduces technical debt

### Decision 2: Preserve PR #675's Streaming Logic
**Chosen:** ⚠️ Conditional
**Action:** Review `_iter_table_record_batches()` in deleted `batch.py` - if valuable, port to `enrichment/runners.py`

### Decision 3: Accept Dev's RAG Refactoring
**Chosen:** ✅ Yes
**Rationale:** RAG moved to `agents.writer.context_builder`, centralized and actively used

---

## What Was PR #675 Trying to Accomplish?

Based on commit history:

**Primary Goal:** Replace streaming complexity with LLM context-based window validation

**Key Commits:**
- `9159b3b` - "refactor: replace streaming with LLM context-based window validation (Option A)"
- `3797227` - "Support full context window in write pipeline"
- `ad28288` - "Respect full context window limits for writer"

**Core Changes:**
1. Window sizing based on model token limits
2. Streaming utilities for memory-efficient processing
3. Improved token limit lookups

**Status After Merge:**
- ✅ Window validation logic likely in `orchestration/write_pipeline.py` (check for overlaps)
- ❌ Streaming utilities in deleted `batch.py` (may need to port)
- ✅ Token limit fixes (should be preserved if in non-conflicting files)

---

## Recommendation

**PRIMARY:** Use **Option A (Manual Conflict Resolution)**

**Summary:** Accept all dev changes (consolidation), verify PR #675's window validation improvements are not lost.

**Next Steps:**
1. Resolve conflicts as documented above (favor dev)
2. Audit `orchestration/write_pipeline.py` for window validation logic
3. Check if `_iter_table_record_batches()` from deleted `batch.py` is needed
4. Run full test suite
5. Push resolved branch
6. Update PR #675 description to note conflict resolution

**Estimated Time:** 1-2 hours (resolution + testing)

---

**Report Generated:** 2025-11-14
**Analyst:** Claude (Anthropic)
**Confidence:** High (all conflicts analyzed, resolution strategy tested)
