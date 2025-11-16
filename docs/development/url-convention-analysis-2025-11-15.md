# URLConvention and MkDocs Adapter Path Analysis - 2025-11-15

Two-level analysis of media enrichment path resolution as requested.

## Level 1: Is URLConvention Correct?

### Current Implementation

**File**: `src/egregora/output_adapters/mkdocs/url_convention.py:117-125`

```python
def _media_enrichment_url(self, document: Document, base: str) -> str:
    """Generate URL for media enrichment."""
    # Use suggested_path or fall back to document_id
    filename = document.suggested_path or f"{document.document_id}.md"

    # Remove prefix if present (same as _determine_media_enrichment_path)
    filename = filename.removeprefix("docs/media/")

    return f"{base}/docs/media/{filename}"
```

### Expected Behavior (from tests)

**Test**: `tests/unit/storage/test_url_convention.py:221`
```python
suggested_path="docs/media/photo.jpg"
# Expected URL: "https://example.com/docs/media/photo.jpg"
```

**Test**: `tests/unit/storage/test_url_convention.py:237`
```python
suggested_path="docs/media/subfolder/photo.jpg"
# Expected URL: "https://example.com/docs/media/subfolder/photo.jpg"
```

### Analysis

The URLConvention expects:
- ✅ **Input**: `suggested_path` with FULL path including `docs/media/` prefix
- ✅ **Output**: URL with `{base}/docs/media/{subpath}`
- ✅ **Behavior**: The `removeprefix()` + re-add pattern allows subdirectories

**Verdict**: URLConvention is CORRECT as designed.

## Level 2: Is the MkDocs Adapter Correct?

### Current Directory Structure

**File**: `src/egregora/output_adapters/mkdocs/adapter.py:243-244`

```python
self.urls_dir = site_root / "docs" / "media" / "urls"  # URL enrichments
self.media_dir = site_root / "docs" / "media"          # Media enrichments
```

### Adapter Path Resolution

**serve()** flow (lines 1091-1114):
```python
def serve(self, document: Document) -> None:
    url = self._url_convention.canonical_url(document, self._ctx)
    path = self._url_to_path(url, document)
    self._write_document(document, path)
```

**_url_to_path()** for ENRICHMENT_MEDIA (lines 1229-1230):
```python
if document.type in (DocumentType.ENRICHMENT_MEDIA, DocumentType.MEDIA):
    return self.site_root / url_path  # url_path already stripped of base
```

### Example Flow

**Without suggested_path** (current behavior):
1. URLConvention: `f"{document.document_id}.md"` → URL: `{base}/docs/media/{uuid}.md`
2. _url_to_path: strips base → `url_path = "docs/media/{uuid}.md"`
3. Returns: `site_root / "docs/media/{uuid}.md"` ✅ CORRECT

**With my incorrect suggested_path** (`media/images/uuid`):
1. URLConvention: `"media/images/uuid"` → `removeprefix("docs/media/")` → no match → `"media/images/uuid"`
2. URLConvention: Returns `{base}/docs/media/media/images/uuid"` ❌ WRONG (double media/)
3. _url_to_path: strips base → `url_path = "docs/media/media/images/uuid"`
4. Returns: `site_root / "docs/media/media/images/uuid"` ❌ WRONG

**Verdict**: MkDocs adapter is CORRECT. My suggested_path was WRONG.

## Root Cause of Issue

### Observed Problem

**File found**: `/home/frank/workspace/blog/042aba52-d110-5b12-9685-52e4f9e36f2d.jpg.md` (ROOT)
**Expected**: `/home/frank/workspace/blog/docs/media/042aba52-d110-5b12-9685-52e4f9e36f2d.md`

### Hypothesis 1: Old Code Path

The file `042aba52...jpg.md` suggests filename is `{uuid}.jpg.md`, not `{uuid}.md`. This pattern indicates:
- Either metadata["filename"] is being used incorrectly
- Or there's an old code path that predates URLConvention

Let me check if there's legacy code still in use.

### Hypothesis 2: My Recent Change

My change at `enrichment/runners.py:364` set `suggested_path = f"media/{media_subdir}/{file_path.stem}"`.

This is WRONG because:
- Missing `docs/` prefix
- URLConvention expects `docs/media/` not `media/`

### Hypothesis 3: Branch State

The user's test run may have been BEFORE my change was committed. If so, the issue is NOT from my change, but from some OTHER bug in the pipeline.

## Required Investigation

1. **Check git blame**: When was the file `042aba52...jpg.md` created? Before or after my recent change?
2. **Check for legacy code**: Search for any code setting paths without using URLConvention
3. **Check actual document creation**: What `suggested_path` value (if any) is being passed when creating ENRICHMENT_MEDIA documents?

## Correct Solution

### Option A: Use URLConvention Correctly

If we want media enrichments in `docs/media/images/`:
```python
# In enrichment/runners.py
media_subdir = media_subdir_map.get(media_type, "files")
suggested_path = f"docs/media/{media_subdir}/{file_path.stem}.md"  # ✅ Includes docs/ prefix
```

URLConvention will:
1. Strip `docs/media/` → `{media_subdir}/{uuid}.md`
2. Re-add `docs/media/` → URL: `{base}/docs/media/{media_subdir}/{uuid}.md`
3. Path: `site_root/docs/media/{media_subdir}/{uuid}.md` ✅ CORRECT

### Option B: Don't Use suggested_path

Keep it simple:
```python
# In enrichment/runners.py
doc = Document(
    content=markdown_content,
    type=DocumentType.ENRICHMENT_MEDIA,
    metadata={"filename": file_path.name, "media_type": media_type},
    # suggested_path=None  (let URLConvention use document_id)
)
```

Path: `docs/media/{uuid}.md` (flat structure)

### Option C: Change URLConvention Design

Modify URLConvention to organize by media type:
```python
def _media_enrichment_url(self, document: Document, base: str) -> str:
    media_type = document.metadata.get("media_type", "files")
    media_subdir_map = {"image": "images", "video": "videos", ...}
    subdir = media_subdir_map.get(media_type, "files")

    filename = document.suggested_path or f"{subdir}/{document.document_id}.md"
    filename = filename.removeprefix("docs/media/")
    return f"{base}/docs/media/{filename}"
```

This would require changing URLConvention behavior (not ideal per user's request to check if it's correct).

## Recommended Action

1. **Revert my suggested_path change** in enrichment/runners.py (it's incorrect)
2. **Find the ACTUAL bug** causing files to end up in root
3. **If we want subdirectories**, use Option A with correct `docs/media/` prefix

## Decision Point for User

**Question**: Where should media enrichment .md files actually go?

- **Option 1**: `docs/media/{uuid}.md` (flat, current design)
- **Option 2**: `docs/media/images/{uuid}.md` (organized by type)
- **Option 3**: `media/images/{uuid}.md` (co-located with actual media files)

Each option requires different implementation:
- Option 1: Keep URLConvention as-is, don't use suggested_path
- Option 2: Use suggested_path with `docs/media/images/` prefix
- Option 3: Requires URLConvention redesign to use `media/` not `docs/media/`

---

## Update: Media Extraction Scope Issue

**CRITICAL**: Media extraction is happening at the WRONG SCOPE.

**Current behavior** (`enrichment/media.py:182-211`):
- `extract_and_replace_media()` processes the ENTIRE messages table
- Extracts ALL media files from the entire conversation at once
- Happens BEFORE windowing

**Expected behavior**:
- Media extraction should be PER-WINDOW
- Each window should only extract media referenced in that window's messages
- Prevents extracting too much media upfront

**Impact**:
- Test run with 31,855 messages extracted 14 media files globally
- Should extract media incrementally as windows are processed
- Allows better control over enrichment budget per window

**Fix required**: Move media extraction INSIDE window processing loop.

---

**Next Steps**:
1. Fix media extraction to be per-window (not global)
2. Test with `--step-size=1 --step-unit=days`
3. Investigate media enrichment path resolution (after scope fix)
4. Fix journal entries
5. Fix URL placeholder validation
