# PR #1372 Review: Banner Generator Path Prediction

## Summary

PR #1372 attempts to make the banner generator functional by predicting the async banner path so that the LLM can reference it in blog posts before the actual banner is generated.

**Status: ⚠️ DOES NOT WORK AS INTENDED**

The predicted path **does not match** the actual path where the banner file will be saved, resulting in broken image references.

## Test Results

I created a test to verify the path prediction logic:

```
Predicted path: media/images/my-awesome-post.jpg
Actual path:    media/files/my-awesome-post
```

**Result**: Paths do not match! ❌

## Issues Found

### 1. Missing File Extension

**Problem**: The actual banner document doesn't include a `filename` in its metadata.

When a banner is generated (in `batch_processor.py:220-224`), the document is created as:

```python
Document(
    content=image_data,
    type=DocumentType.MEDIA,
    metadata={
        "mime_type": mime_type,
        "slug": task.slug,
        "language": task.language,
        "task_id": task.task_id
    }
    # NO id field, NO filename in metadata
)
```

Without an explicit filename, the `_format_media` URL convention uses:
```python
fname = doc.metadata.get("filename", doc.document_id)
```

Since there's no filename, it falls back to `doc.document_id`, which is just the slugified slug (e.g., "my-awesome-post") **without any file extension**.

**Impact**: The saved file has no extension, making it unrecognizable by browsers and markdown renderers.

### 2. Wrong Subfolder

**Problem**: The subfolder is determined by the file extension.

The `get_media_subfolder()` function (in `ops/media.py:90-104`) determines the subfolder based on file extension:
- `.jpg`, `.jpeg`, `.png`, etc. → `images/`
- No extension or unknown → `files/`

Since the actual banner has no extension, it goes to `files/` instead of `images/`.

**PR #1372 assumes**: `images/` subfolder
**Actual location**: `files/` subfolder

### 3. Extension Assumption

**Problem**: The PR hardcodes `.jpg` extension.

Line 99 of the PR:
```python
document_id = f"{slug}.jpg"
```

This assumes all banners will be JPEG, but:
- The Gemini API might return PNG or other formats
- The `mime_type` metadata already contains the correct format
- Hardcoding creates a mismatch with the actual mime type

## Root Cause

The fundamental issue is that **banner documents don't store their filename in metadata**. The path prediction tries to work around this by creating a placeholder document, but it can't accurately predict what the actual document ID and path will be without knowing the persistence logic.

## Recommended Fix

To properly fix this issue, we need to ensure the banner document includes proper filename metadata **at creation time**:

### Option 1: Add Filename to Banner Metadata (Recommended)

Modify `batch_processor.py:_create_document()` to include a proper filename with extension:

```python
def _create_document(
    self,
    task: BannerTaskEntry,
    image_data: bytes,
    mime_type: str,
    *,
    extra_metadata: dict[str, Any] | None = None,
) -> Document:
    metadata = self._build_metadata(task, extra_metadata)
    metadata["mime_type"] = mime_type

    # NEW: Add proper filename with extension based on mime_type
    extension = self._get_extension_for_mime_type(mime_type)
    slug = slugify(task.slug, max_len=60)
    filename = f"{slug}{extension}"

    return Document(
        content=image_data,
        type=DocumentType.MEDIA,
        metadata={**metadata, "filename": filename},
        id=filename  # Use filename as explicit ID for consistency
    )

def _get_extension_for_mime_type(self, mime_type: str) -> str:
    """Map MIME type to file extension."""
    mime_to_ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mime_to_ext.get(mime_type, ".jpg")
```

Then, update the path prediction in `capabilities.py` to match:

```python
# Predict the path using the same logic as banner generation
from egregora.ops.media import get_media_subfolder

slug = slugify(post_slug, max_len=60)

# Gemini typically returns JPEG, but check config if available
extension = ".jpg"  # Default assumption
filename = f"{slug}{extension}"

# Create placeholder with proper filename and ID
placeholder_doc = Document(
    content="",
    type=DocumentType.MEDIA,
    metadata={"filename": filename},
    id=filename
)

# Generate URL using the output sink's convention
output_sink = ctx.deps.resources.output
predicted_url = output_sink.url_convention.canonical_url(
    placeholder_doc,
    output_sink.url_context
)

return BannerResult(
    status="scheduled",
    path=predicted_url.lstrip("/")
)
```

### Option 2: Use Suggested Path

Alternatively, set a `suggested_path` on the banner document that gets preserved during persistence:

```python
# In batch_processor
document = Document(
    content=image_data,
    type=DocumentType.MEDIA,
    metadata=metadata,
    suggested_path=f"posts/media/images/{slug}.jpg"
)
```

This way, the `_format_media` URL convention will use the suggested path directly.

## Additional Issues

### Line 118-121: Redundant Fallback

```python
else:
    # Fallback if no output sink available (should not happen in writer)
    predicted_url = self.url_convention.canonical_url(
        placeholder_doc, ctx.deps.resources.output.url_context
    )
```

This fallback code accesses `ctx.deps.resources.output.url_context` even though the condition checks that `output_sink` (which IS `ctx.deps.resources.output`) is falsy. This will raise an `AttributeError`.

**Fix**: Remove the fallback or handle the case properly:
```python
else:
    # Fallback: use default convention without context
    from egregora.data_primitives.protocols import UrlContext
    predicted_url = self.url_convention.canonical_url(
        placeholder_doc,
        UrlContext(base_url="", site_prefix="")
    )
```

### Line 66: Unnecessary Instance Variable

```python
self.url_convention = StandardUrlConvention()
```

This creates a duplicate URL convention instance when the output sink already has one. Better to just use `ctx.deps.resources.output.url_convention` directly.

## Testing Recommendations

1. **Add integration test**: Create a test that:
   - Schedules a banner generation
   - Waits for the worker to process it
   - Verifies the predicted path matches the actual saved path

2. **Add unit test**: Test the path prediction logic with different:
   - MIME types (JPEG, PNG, WebP)
   - Slug lengths
   - Special characters in slugs

3. **Test with real Gemini API**: Verify that actual Gemini responses work correctly with the provided API key

## Conclusion

The PR is a good attempt to solve the async banner path prediction problem, but it doesn't work correctly due to:
1. Missing filename/extension in actual banner documents
2. Mismatched subfolder logic
3. Hardcoded assumptions

The root cause needs to be fixed in the banner generation code itself to include proper filename metadata, then the path prediction can accurately match it.

## Recommendation

**DO NOT MERGE** as-is. Implement Option 1 above to fix the root cause first, then update the path prediction logic to match.
