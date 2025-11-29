# URL Convention / Output Adapter Separation of Concerns

## Executive Summary

This PR refactors the URL generation system to strictly separate **logical URL concerns** (UrlConvention) from **filesystem path concerns** (OutputAdapter), following the principle:

> **URL ⟶ concern of the URL convention**
> **Filesystem path / artifact layout ⟶ concern of the output adapter**

**Current State:** The `StandardUrlConvention` class violates this principle by importing and using `Path` operations to manipulate URL strings, mixing logical URL generation with filesystem concerns.

**Goal:** Establish a clean separation where UrlConvention produces pure URL strings and OutputAdapter handles all filesystem path resolution.

---

## Problems Identified

### Critical Violation: UrlConvention Uses Path Operations

**File:** `src/egregora/output_adapters/conventions.py`

**Line 7:**
```python
from pathlib import Path  # ❌ VIOLATION: UrlConvention should not know about filesystem paths
```

**Lines 94, 138, 142:**
```python
# Line 94 - canonical_url() for ENRICHMENT_URL
clean_path = Path(document.suggested_path.strip("/")).with_suffix("").as_posix()

# Line 138 - _format_media_enrichment_url()
enrichment_path = Path(parent_path).with_suffix("").as_posix()

# Line 142 - _format_media_enrichment_url() fallback
clean_path = Path(document.suggested_path.strip("/")).with_suffix("").as_posix()
```

**Why This Is Wrong:**

1. **Responsibility Leak:** UrlConvention is doing filesystem path manipulation (`.with_suffix()`, `.as_posix()`)
2. **Wrong Abstraction:** URLs don't have "suffixes" - that's a filesystem concept
3. **Coupling:** Makes it impossible to have pure URL conventions that work with non-filesystem backends (S3, database, etc.)

---

## Refined Responsibility Split

### a) UrlConvention – Purely Logical, No Filesystem

**What it does:**
- Given a `Document`, return what URL readers should use
- Pure string manipulation
- No knowledge of `Path`, `docs_dir`, `site_dir`, `mkdocs.yml`, etc.
- Only uses `doc.type`, `slug`, `tags`, `date`, etc.

**Protocol:**
```python
class UrlConvention(Protocol):
    def url_for(self, doc: Document, ctx: UrlContext) -> str:
        """Return a logical URL like '/posts/foo-bar/' or '/media/xyz.png'."""
```

**Characteristics:**
- No `from pathlib import Path`
- Only string operations (`str.split()`, `str.strip()`, `str.replace()`)
- Can be plugged by config: `MkdocsBlogConvention`, `MkdocsFlatConvention`, `JsonApiConvention`

---

### b) OutputAdapter – Decides Where and How to Persist

**What it does:**
- Takes Document, calls convention to get URL, decides filesystem layout
- Converts URLs to filesystem paths
- Handles `docs/`, `media/`, `index.md` vs `foo.md` quirks

**Example:**
```python
class MkdocsOutputAdapter:
    def __init__(self, base_dir: Path, convention: UrlConvention):
        self.base_dir = base_dir
        self.convention = convention

    def persist(self, doc: Document) -> str:
        url = self.convention.canonical_url(doc, self.ctx)  # '/posts/foo-bar/'
        path = self._url_to_path(url, doc)                   # docs/posts/foo-bar.md
        self._write_to_disk(path, doc)
        return url
```

**Key Point:**
- The `_url_to_path()` method is where filesystem concerns live
- Adapter decides: "URL X maps to file Y.md or Y/index.md"
- Core never sees `Path` except during bootstrap

---

## Refactoring Strategy

### Phase 1: Fix UrlConvention - Remove Path Operations (Priority: HIGH)

**Goal:** Make `StandardUrlConvention.canonical_url()` use only string operations.

#### 1.1 Replace Path Operations with String Manipulation

**File:** `src/egregora/output_adapters/conventions.py`

**Before (Line 94):**
```python
if document.suggested_path:
    clean_path = Path(document.suggested_path.strip("/")).with_suffix("").as_posix()
    return self._join(ctx, clean_path, trailing_slash=True)
```

**After:**
```python
if document.suggested_path:
    # Pure string manipulation - no Path operations
    clean_path = document.suggested_path.strip("/")
    # Remove file extension if present (URL logic, not filesystem logic)
    if "." in clean_path:
        clean_path = clean_path.rsplit(".", 1)[0]
    return self._join(ctx, clean_path, trailing_slash=True)
```

**Before (Line 138):**
```python
if parent_path:
    enrichment_path = Path(parent_path).with_suffix("").as_posix()
    return self._join(ctx, enrichment_path.strip("/"), trailing_slash=True)
```

**After:**
```python
if parent_path:
    # Pure string manipulation
    enrichment_path = parent_path.strip("/")
    if "." in enrichment_path:
        enrichment_path = enrichment_path.rsplit(".", 1)[0]
    return self._join(ctx, enrichment_path, trailing_slash=True)
```

**Before (Line 142):**
```python
if document.suggested_path:
    clean_path = Path(document.suggested_path.strip("/")).with_suffix("").as_posix()
    return self._join(ctx, clean_path, trailing_slash=True)
```

**After:**
```python
if document.suggested_path:
    clean_path = document.suggested_path.strip("/")
    if "." in clean_path:
        clean_path = clean_path.rsplit(".", 1)[0]
    return self._join(ctx, clean_path, trailing_slash=True)
```

#### 1.2 Remove Path Import

**File:** `src/egregora/output_adapters/conventions.py`

**Before (Line 7):**
```python
from pathlib import Path
```

**After:**
```python
# Removed - UrlConvention is purely logical, no filesystem operations
```

**Files Changed:**
- `src/egregora/output_adapters/conventions.py` (-1 import, ~6 line changes)

---

### Phase 2: Document the Separation of Concerns (Priority: HIGH)

**Goal:** Make the principle explicit in documentation and code comments.

#### 2.1 Add Module-Level Documentation

**File:** `src/egregora/output_adapters/conventions.py`

Add at top of file:
```python
"""Standard URL conventions for Egregora output adapters.

SEPARATION OF CONCERNS (2025-11-29):
=====================================

This module implements UrlConvention protocol - PURELY LOGICAL URL GENERATION.

What UrlConvention does:
- Given a Document, return what URL readers should use
- Pure string manipulation only
- No filesystem knowledge (no Path, no docs_dir, no file extensions)
- Uses only doc.type, slug, tags, date metadata

What UrlConvention does NOT do:
- Filesystem path resolution (that's OutputAdapter's job)
- File layout decisions (index.md vs foo.md)
- Directory structure (docs/, media/, etc.)

Examples:
    >>> convention = StandardUrlConvention()
    >>> ctx = UrlContext(base_url="https://example.com", site_prefix="blog")
    >>> doc = Document(type=DocumentType.POST, metadata={"slug": "hello", "date": "2025-01-10"})
    >>> convention.canonical_url(doc, ctx)
    'https://example.com/blog/posts/2025-01-10-hello/'

The OutputAdapter then converts this URL to a filesystem path:
    >>> adapter.persist(doc)  # Internally: URL -> Path("docs/posts/2025-01-10-hello.md")
"""
```

#### 2.2 Update Protocol Documentation

**File:** `src/egregora/data_primitives/protocols.py`

Enhance `UrlConvention` protocol docstring (lines 60-73):

**Before:**
```python
class UrlConvention(Protocol):
    """Contract for deterministic URL generation strategies."""
```

**After:**
```python
class UrlConvention(Protocol):
    """Contract for deterministic URL generation strategies.

    CRITICAL: This is a PURELY LOGICAL protocol. Implementations must:
    - Use ONLY string operations (no Path, no filesystem concepts)
    - Return URLs as strings ('/posts/foo/' or 'https://example.com/posts/foo/')
    - Have NO knowledge of filesystem layout (docs_dir, file extensions, etc.)

    Filesystem path resolution is the responsibility of OutputAdapter implementations,
    not UrlConvention. This separation enables:
    - Pure URL conventions that work with any backend (filesystem, S3, database)
    - Clean testing of URL logic without filesystem dependencies
    - Flexibility to change file layouts without changing URL structure

    Example of correct implementation:
        class MyConvention(UrlConvention):
            def canonical_url(self, doc: Document, ctx: UrlContext) -> str:
                # ✅ String manipulation only
                slug = doc.metadata.get("slug", doc.document_id[:8])
                return f"{ctx.base_url}/posts/{slug}/"

    Example of INCORRECT implementation:
        class BadConvention(UrlConvention):
            def canonical_url(self, doc: Document, ctx: UrlContext) -> str:
                # ❌ WRONG: Using Path operations
                path = Path(doc.suggested_path).with_suffix("").as_posix()
                return f"{ctx.base_url}/{path}/"
    """
```

**Files Changed:**
- `src/egregora/output_adapters/conventions.py` (+30 lines module docstring)
- `src/egregora/data_primitives/protocols.py` (+25 lines protocol docstring)

---

### Phase 3: Add Helper for Extension Removal (Priority: MEDIUM)

**Goal:** Extract string-based extension removal logic to a reusable helper.

#### 3.1 Create URL Utility Function

**File:** `src/egregora/output_adapters/conventions.py`

Add helper function:
```python
def _remove_url_extension(url_path: str) -> str:
    """Remove file extension from URL path segment.

    This is URL logic (removing trailing .html, .md, etc. from URLs),
    not filesystem logic (Path.with_suffix). URLs may contain dots
    that aren't extensions, so we only remove extensions from the
    last path segment.

    Args:
        url_path: URL path like 'media/images/foo.png' or 'posts/bar'

    Returns:
        URL path without extension: 'media/images/foo' or 'posts/bar'

    Examples:
        >>> _remove_url_extension("media/images/foo.png")
        'media/images/foo'
        >>> _remove_url_extension("posts/bar")
        'posts/bar'
        >>> _remove_url_extension("some.dir/file.md")
        'some.dir/file'
    """
    if "." in url_path:
        # Split only on the last dot of the last path segment
        parts = url_path.rsplit("/", 1)
        if len(parts) == 2 and "." in parts[1]:
            # Has a path and a filename with extension
            return f"{parts[0]}/{parts[1].rsplit('.', 1)[0]}"
        elif "." in parts[0]:
            # Just a filename with extension
            return parts[0].rsplit(".", 1)[0]
    return url_path
```

#### 3.2 Use Helper in canonical_url()

**Before:**
```python
clean_path = document.suggested_path.strip("/")
if "." in clean_path:
    clean_path = clean_path.rsplit(".", 1)[0]
```

**After:**
```python
clean_path = _remove_url_extension(document.suggested_path.strip("/"))
```

**Files Changed:**
- `src/egregora/output_adapters/conventions.py` (+25 lines helper, ~6 call sites)

---

### Phase 4: Add Tests for Pure String Logic (Priority: MEDIUM)

**Goal:** Ensure UrlConvention uses only strings, no Path operations.

#### 4.1 Create Unit Tests

**File:** `tests/unit/output_adapters/test_conventions.py`

```python
"""Unit tests for UrlConvention implementations.

Tests verify that UrlConvention uses ONLY string operations,
no Path or filesystem dependencies.
"""

import pytest
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlContext
from egregora.output_adapters.conventions import StandardUrlConvention, _remove_url_extension


class TestUrlExtensionRemoval:
    """Test pure string-based extension removal."""

    def test_removes_extension_from_simple_path(self):
        assert _remove_url_extension("file.md") == "file"
        assert _remove_url_extension("image.png") == "image"

    def test_removes_extension_from_nested_path(self):
        assert _remove_url_extension("media/images/foo.png") == "media/images/foo"
        assert _remove_url_extension("posts/2025-01-10.md") == "posts/2025-01-10"

    def test_preserves_dots_in_directory_names(self):
        assert _remove_url_extension("some.dir/file.md") == "some.dir/file"
        assert _remove_url_extension("v1.0/api.json") == "v1.0/api"

    def test_handles_no_extension(self):
        assert _remove_url_extension("posts/hello") == "posts/hello"
        assert _remove_url_extension("media/video") == "media/video"


class TestStandardUrlConventionPurity:
    """Verify StandardUrlConvention uses only strings, no Path operations."""

    @pytest.fixture
    def convention(self):
        return StandardUrlConvention()

    @pytest.fixture
    def ctx(self):
        return UrlContext(base_url="https://example.com", site_prefix="blog")

    def test_post_url_is_pure_string(self, convention, ctx):
        doc = Document(
            type=DocumentType.POST,
            content="Test post",
            metadata={"slug": "hello-world", "date": "2025-01-10"},
        )
        url = convention.canonical_url(doc, ctx)
        assert url == "https://example.com/blog/posts/2025-01-10-hello-world/"
        assert isinstance(url, str)

    def test_enrichment_url_removes_extension_via_string_ops(self, convention, ctx):
        """Verify extension removal uses string ops, not Path.with_suffix()."""
        doc = Document(
            type=DocumentType.ENRICHMENT_URL,
            content="Enrichment",
            suggested_path="media/urls/article.html",
        )
        url = convention.canonical_url(doc, ctx)
        # Should remove .html extension via string manipulation
        assert ".html" not in url
        assert "article" in url

    def test_media_enrichment_preserves_path_structure(self, convention, ctx):
        """Verify path manipulation uses string ops, not Path.as_posix()."""
        parent = Document(
            type=DocumentType.MEDIA,
            content=b"image data",
            suggested_path="media/images/photo.jpg",
        )
        doc = Document(
            type=DocumentType.ENRICHMENT_MEDIA,
            content="Photo description",
            parent=parent,
        )
        url = convention.canonical_url(doc, ctx)
        # Should use parent path structure via string ops
        assert "media/images/photo" in url
        assert ".jpg" not in url  # Extension removed via string ops


class TestUrlConventionNoFilesystemDependency:
    """Ensure UrlConvention has NO filesystem dependencies."""

    def test_no_path_import_in_conventions_module(self):
        """Verify conventions.py does not import pathlib.Path."""
        import egregora.output_adapters.conventions as conventions_module

        # Check module doesn't have Path in its namespace
        assert not hasattr(conventions_module, "Path")

        # Verify by checking source
        import inspect
        source = inspect.getsource(conventions_module)
        assert "from pathlib import Path" not in source
        assert "import pathlib" not in source
```

**Files Changed:**
- `tests/unit/output_adapters/test_conventions.py` (+100 lines, new file)

---

### Phase 5: Update CLAUDE.md with Principle (Priority: LOW)

**Goal:** Document this architectural principle for future development.

#### 5.1 Add to Design Principles

**File:** `CLAUDE.md`

Add new principle after line 98 (in `## Design Principles` section):

```markdown
✅ **URL/Path Separation:** UrlConvention = pure URL logic (strings only), OutputAdapter = filesystem paths
```

#### 5.2 Add to Architecture Section

**File:** `CLAUDE.md`

Add new subsection after line 167 (in `## Architecture` section):

```markdown
### URL Convention vs Output Adapter Separation

**Critical Principle:** URL generation and filesystem path resolution are separate concerns.

**UrlConvention (Purely Logical):**
- Given Document → return URL string
- Uses ONLY string operations (`str.split()`, `str.strip()`, etc.)
- No `Path`, no filesystem concepts
- Examples: `/posts/hello/`, `https://example.com/media/image.png`

**OutputAdapter (Filesystem Layout):**
- Takes URL from convention → resolves to filesystem path
- Handles `docs/`, `media/`, `index.md` vs `foo.md`
- Knows about MkDocs quirks, file extensions, directory structure

**Why This Matters:**
- UrlConvention works with any backend (filesystem, S3, database, CMS)
- URL structure stable across output format changes
- Clean testing (no filesystem mocking for URL logic)

**Example:**
```python
# ✅ CORRECT: UrlConvention uses strings
class MkdocsBlogConvention(UrlConvention):
    def canonical_url(self, doc: Document, ctx: UrlContext) -> str:
        slug = doc.metadata.get("slug")
        return f"{ctx.base_url}/posts/{slug}/"

# ❌ WRONG: UrlConvention uses Path
class BadConvention(UrlConvention):
    def canonical_url(self, doc: Document, ctx: UrlContext) -> str:
        path = Path(doc.suggested_path).with_suffix("")  # NO!
        return f"{ctx.base_url}/{path.as_posix()}/"      # NO!
```

**See:** `docs/architecture/protocols.md#url-generation`
```

**Files Changed:**
- `CLAUDE.md` (+45 lines in Design Principles and Architecture sections)

---

## Implementation Plan

### Sprint 1: Core Refactoring (Priority: HIGH)
- [x] **Task 1.1:** Remove `Path` import from `conventions.py`
- [x] **Task 1.2:** Replace `Path().with_suffix()` with string operations (3 locations)
- [x] **Task 1.3:** Replace `Path().as_posix()` with string operations (3 locations)
- [x] **Task 1.4:** Add module-level documentation explaining separation

**Time Estimate:** 2 hours
**Risk:** Low (purely refactoring, no behavior change)

### Sprint 2: Testing & Validation (Priority: HIGH)
- [ ] **Task 2.1:** Create unit tests for string-based extension removal
- [ ] **Task 2.2:** Add tests verifying no Path operations in UrlConvention
- [ ] **Task 2.3:** Run existing test suite to verify no regressions
- [ ] **Task 2.4:** Add integration tests for URL → Path conversion in adapter

**Time Estimate:** 3 hours
**Risk:** Low (tests only, no production code changes)

### Sprint 3: Documentation (Priority: MEDIUM)
- [ ] **Task 3.1:** Update `UrlConvention` protocol docstring
- [ ] **Task 3.2:** Add helper function docstrings
- [ ] **Task 3.3:** Update CLAUDE.md Design Principles section
- [ ] **Task 3.4:** Update CLAUDE.md Architecture section

**Time Estimate:** 1.5 hours
**Risk:** None (documentation only)

---

## Success Criteria

1. **No Path operations in UrlConvention:**
   - `conventions.py` does not import `pathlib.Path`
   - All extension removal uses string operations
   - All path manipulation uses string operations

2. **Tests verify purity:**
   - Unit tests confirm string-only operations
   - Tests verify no Path in module namespace
   - Integration tests verify adapter converts URLs to paths

3. **Documentation is clear:**
   - Module docstrings explain separation
   - Protocol docstrings show correct/incorrect examples
   - CLAUDE.md documents the principle

4. **No behavior changes:**
   - All existing tests pass
   - URL generation produces same results
   - No changes to public API

---

## Files Modified Summary

| File | Changes | Lines |
|------|---------|-------|
| `src/egregora/output_adapters/conventions.py` | Remove Path, add string ops, add docs | -1, +60 |
| `src/egregora/data_primitives/protocols.py` | Enhance UrlConvention docstring | +25 |
| `tests/unit/output_adapters/test_conventions.py` | New test file | +100 |
| `CLAUDE.md` | Add principle to Design & Architecture | +45 |
| **Total** | **4 files** | **~230 lines** |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| String ops differ from Path ops | Low | Medium | Careful testing, verify same outputs |
| Edge cases in extension removal | Medium | Low | Comprehensive unit tests |
| Breaking URL generation | Low | High | Run full test suite, manual verification |
| Documentation out of sync | Low | Low | Update docs in same PR |

---

## Rollback Plan

If refactoring causes issues:

1. **Immediate:** Revert to previous commit (single PR, easy rollback)
2. **String op bugs:** Fix edge cases in `_remove_url_extension()`
3. **Test failures:** Investigate differences between Path and string ops
4. **Performance issues:** Profile and optimize string operations

---

## References

- **User Request:** "URL → concern of UrlConvention, Filesystem path → concern of OutputAdapter"
- **Current Code:** `src/egregora/output_adapters/conventions.py:7,94,138,142`
- **Protocol Definition:** `src/egregora/data_primitives/protocols.py:60-73`
- **Design Principle:** Separation of Concerns (ISP-compliant protocols)

---

## Verification Steps

After implementation, verify:

1. **No Path imports:**
   ```bash
   grep -n "from pathlib import Path" src/egregora/output_adapters/conventions.py
   # Should return: no matches
   ```

2. **No Path operations:**
   ```bash
   grep -n "Path(" src/egregora/output_adapters/conventions.py
   # Should return: no matches
   ```

3. **All tests pass:**
   ```bash
   uv run pytest tests/unit/output_adapters/test_conventions.py -v
   uv run pytest tests/ -v
   ```

4. **URL generation unchanged:**
   ```bash
   # Compare URL generation before/after for sample documents
   uv run python -c "from egregora.output_adapters.conventions import StandardUrlConvention; ..."
   ```

---

## PR Checklist

- [ ] `Path` import removed from `conventions.py`
- [ ] All `Path().with_suffix()` replaced with string ops
- [ ] All `Path().as_posix()` replaced with string ops
- [ ] Helper function `_remove_url_extension()` added with docstring
- [ ] Module docstring explains separation of concerns
- [ ] Protocol docstring enhanced with examples
- [ ] Unit tests verify string-only operations
- [ ] Unit tests verify no Path in module namespace
- [ ] Full test suite passes (`pytest tests/`)
- [ ] CLAUDE.md Design Principles updated
- [ ] CLAUDE.md Architecture section updated
- [ ] Code review requested
- [ ] No behavior changes verified
