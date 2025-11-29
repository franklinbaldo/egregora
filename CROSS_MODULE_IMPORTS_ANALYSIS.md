# Cross-Module Private Import Analysis

**Date:** 2025-11-29
**Issue:** Private functions (prefixed with `_`) imported across module boundaries

---

## Summary

Found **3 instances** of anti-pattern imports:

1. ✅ **Acceptable:** `_safe_yaml_load` - Explicitly exported in `__all__`
2. ⚠️ **Code Smell:** `_build_conversation_xml` - Private function imported publicly
3. 🔴 **CRITICAL BUG:** `_generate_fallback_avatar_url` - **Function doesn't exist!**

---

## Issue 1: `_safe_yaml_load` (Acceptable)

**Location:** `src/egregora/output_adapters/mkdocs/adapter.py:31`

```python
from egregora.output_adapters.mkdocs.scaffolding import MkDocsSiteScaffolder, _safe_yaml_load
```

**Analysis:**
- Function `_safe_yaml_load` is defined in `scaffolding.py:36`
- Explicitly exported in `__all__` list (line 289)
- Used in `adapter.py:329`

**Status:** ✅ **Acceptable** - Underscore is stylistic choice, function is intentionally public

**Recommendation:** Consider renaming to `safe_yaml_load` (without underscore) since it's public API

---

## Issue 2: `_build_conversation_xml` (Code Smell)

**Location:** `src/egregora/transformations/windowing.py:39`

```python
from egregora.agents.formatting import _build_conversation_xml
```

**Analysis:**
- Function `_build_conversation_xml` is private (underscore prefix)
- NOT in `__all__` list (no `__all__` in `formatting.py`)
- Imported across module boundary

**Status:** ⚠️ **Code Smell** - Violates encapsulation

**Recommendation:**
1. **Option A (Preferred):** Make it public by removing underscore prefix
   - Rename to `build_conversation_xml`
   - Add to `__all__` in `formatting.py`
2. **Option B:** Move function to a shared module
3. **Option C:** Duplicate the logic in `windowing.py` (if small)

**Impact:** Medium - Function works but violates design principles

---

## Issue 3: `_generate_fallback_avatar_url` (CRITICAL BUG) 🔴

**Locations:**
- `src/egregora/output_adapters/mkdocs/adapter.py:1008`
- `src/egregora/output_adapters/mkdocs/adapter.py:1115`

```python
from egregora.knowledge.profiles import _generate_fallback_avatar_url
```

**Analysis:**
- **Function does NOT exist!**
- Actual function name: `generate_fallback_avatar_url` (no underscore)
- Located in `profiles.py:227`
- Import will fail at runtime with `ImportError`

**Verification:**
```bash
$ uv run python -c "from egregora.knowledge.profiles import _generate_fallback_avatar_url"
ImportError: cannot import name '_generate_fallback_avatar_url' from 'egregora.knowledge.profiles'
Did you mean: 'generate_fallback_avatar_url'?
```

**Status:** 🔴 **CRITICAL BUG** - Code will crash if executed

**Why This Wasn't Caught:**
- Import is inside a function (lazy import)
- Code path may not be covered by tests
- Test fixtures may provide avatar data, skipping fallback generation

**Fix Required:**
```diff
- from egregora.knowledge.profiles import _generate_fallback_avatar_url
- avatar = _generate_fallback_avatar_url(author_uuid)
+ from egregora.knowledge.profiles import generate_fallback_avatar_url
+ avatar = generate_fallback_avatar_url(author_uuid)
```

**Files to Fix:**
1. `src/egregora/output_adapters/mkdocs/adapter.py:1008`
2. `src/egregora/output_adapters/mkdocs/adapter.py:1115`

---

## Recommended Actions

### Immediate (Critical)
1. ✅ Fix `_generate_fallback_avatar_url` import bug (2 locations)
2. ✅ Add test coverage for fallback avatar generation path

### Short-term (Code Quality)
3. Make `_build_conversation_xml` public by removing underscore
4. Optionally rename `_safe_yaml_load` to `safe_yaml_load`

### Long-term (Process)
5. Add linting rule to detect private imports across modules
6. Add integration test for fallback avatar code path

---

## Verification Commands

```bash
# Check for all private imports
grep -r "from .* import _[a-zA-Z]" src/

# Test specific imports
uv run python -c "from egregora.agents.formatting import _build_conversation_xml"
uv run python -c "from egregora.knowledge.profiles import _generate_fallback_avatar_url"  # Should fail
uv run python -c "from egregora.knowledge.profiles import generate_fallback_avatar_url"  # Should work
```

---

## Impact Assessment

**Critical Bug Impact:**
- **Severity:** High
- **Probability:** Medium-Low (only triggered when avatar is missing)
- **Affected Code:** MkDocs adapter profile generation
- **User Impact:** Site generation will fail for users without avatars

**Code Smell Impact:**
- **Severity:** Low
- **Probability:** N/A (already in use, works correctly)
- **Affected Code:** Windowing/formatting coordination
- **User Impact:** None (functional issue, not runtime issue)

---

## Additional Notes

The fact that this bug exists suggests:
1. Test coverage gaps in avatar fallback code path
2. No integration tests for profile generation without avatars
3. Linting rules don't catch cross-module private imports

This is exactly the kind of issue a comprehensive dead code analysis helps uncover!
