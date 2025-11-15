# Output Issues Investigation - 2025-11-15

Investigation of issues found in blog output generated on dev branch after schema validation fixes.

## Test Environment

- **Branch**: `fix/schema-validation-mismatch-dev`
- **Input**: real-whatsapp-export.zip (31,855 messages)
- **Output**: `/home/frank/workspace/blog`
- **Configuration**: `--step-size=100 --step-unit=messages`
- **Run Status**: Completed with partial success

## Successful Outputs

✅ **Blog Posts** - 3 posts generated in `/posts/`:
- `2025-03-03-language-entropy-academic-babel-collapse.md` (3.6KB)
- `2025-03-03-semantic-entropy-and-the-babel-collapse.md` (4.4KB)
- `2025-03-03-the-geometry-of-the-superbaby-emptying-the-self.md` (3.5KB)

Content quality appears good - rich, well-formatted Markdown with proper frontmatter.

✅ **URL Enrichments** - 25 enriched URLs in `/media/urls/`:
- Proper UUID-based filenames (e.g., `https-arxiv-org-abs-2502-15840-b4ef9039.md`)
- Most have content

✅ **Media Extraction** - 14 images extracted to `/media/images/`:
- UUID-based filenames (e.g., `f3c25bd4-cc41-5e2f-9a68-20ed9b6d6f2f.jpg`)
- Files exist and are valid images

✅ **Author Profiles** - Multiple profiles created in `/profiles/`:
- UUID-based filenames matching author UUIDs
- Proper YAML frontmatter

## Issues Found

### 1. Journal Entries Not Created

**Location**: `/home/frank/workspace/blog/posts/journal/`
**Current State**: Empty (only `.gitkeep` file)
**Expected**: Journal entries from writer agent execution

**Evidence**:
```bash
$ ls -la /home/frank/workspace/blog/posts/journal/
total 8
drwxr-xr-x 2 frank frank 4096 Nov 15 16:00 .
drwxr-xr-x 3 frank frank 4096 Nov 15 16:05 ..
-rw-r--r-- 1 frank frank    0 Nov 15 16:00 .gitkeep
```

**Investigation**:
- Journal template exists: `src/egregora/templates/journal.md.jinja` ✓
- `_save_journal_to_file()` function exists in `agents/writer/agent.py` ✓
- Function is called after agent execution (line 694) ✓
- Early returns possible:
  - If `intercalated_log` is empty (line 254)
  - If templates directory not found (line 260)
  - If template loading fails (line 269)
  - If template rendering fails (line 282)
  - If serve() fails (line 297)

**Hypothesis**: The intercalated log may be empty, OR there's a silent failure in template rendering/serving that's being caught by the broad exception handler.

**Next Steps**:
- Check logs for "Failed to load journal template" or "Failed to write journal"
- Add debug logging to see if `intercalated_log` is populated
- Verify OutputAdapter.serve() is handling DocumentType.JOURNAL correctly

### 2. URL Enrichment Placeholders

**File**: `/home/frank/workspace/blog/media/urls/https-breakingthenews-net-article-bessen-75bea96f.md`
**Current Content**: `URL_CONTENT_GROUNDING`
**Expected**: Actual enriched content from URL

**Evidence**:
```bash
$ cat /home/frank/workspace/blog/media/urls/https-breakingthenews-net-article-bessen-75bea96f.md
URL_CONTENT_GROUNDING
```

**Investigation**:
- Searched codebase for "URL_CONTENT_GROUNDING" - **not found in source code** ❌
- This suggests the placeholder is coming from:
  - External LLM response
  - Cache corruption
  - Failed WebFetch/enrichment that left partial content

**Hypothesis**: The LLM enrichment agent failed or returned a placeholder response that wasn't caught as an error.

**Next Steps**:
- Check enrichment cache for this URL
- Review LLM agent error handling
- Check if this is a Gemini API response pattern

### 3. Media Enrichment in Wrong Location

**File**: `/home/frank/workspace/blog/042aba52-d110-5b12-9685-52e4f9e36f2d.jpg.md`
**Current Location**: Root of blog
**Expected Location**: `/media/images/` or `/enrichments/`

**Evidence**:
```bash
$ cat /home/frank/workspace/blog/042aba52-d110-5b12-9685-52e4f9e36f2d.jpg.md
This media file is a March 2025 calendar tracking the international travel
itinerary for a person named Carolina...
```

**Content**: Has valid media description (452 bytes)
**Problem**: File is in wrong location (root instead of organized media directory)

**Investigation**:
- Filename pattern suggests it's a media enrichment (.jpg.md suffix)
- The `.jpg` file exists in `/media/images/` with same UUID base
- The enrichment .md file should be alongside or in enrichments/

**Hypothesis**: OutputAdapter.serve() for DocumentType.ENRICHMENT_MEDIA is using wrong path resolution.

**Next Steps**:
- Check MkDocsOutputAdapter.serve() handling of ENRICHMENT_MEDIA type
- Review url_convention.py for media enrichment path logic
- Verify expected directory structure for enrichments

### 4. Missing Enrichments Directory

**Expected**: `/home/frank/workspace/blog/enrichments/`
**Current State**: Does not exist

**Expected Structure**:
```
blog/
├── enrichments/
│   ├── media/
│   │   └── {uuid}.md  # Media descriptions
│   └── urls/
│       └── {uuid}.md  # URL content
├── media/
│   ├── images/
│   │   └── {uuid}.jpg  # Actual media files
│   └── ...
```

**Current Structure**:
```
blog/
├── {uuid}.jpg.md  # ❌ In root instead of enrichments/media/
├── media/
│   ├── images/
│   │   └── {uuid}.jpg  # ✓ Correct
│   └── urls/
│       └── {hash}.md  # ✓ But should these be in enrichments/urls/?
```

**Hypothesis**: The output adapter may have changed structure, or enrichments/ was never implemented on dev branch.

**Next Steps**:
- Review MkDocs output adapter directory structure
- Check if enrichments/ is legacy or current design
- Determine correct location for enrichment .md files

### 5. Missing .md Files for Images

**Location**: `/home/frank/workspace/blog/media/images/`
**Current State**: Only `.jpg` files, no `.md` enrichments
**Expected**: Each image should have a corresponding `.md` file with description

**Evidence**:
```bash
$ find /home/frank/workspace/blog/media/images -name "*.md"
# No results (except .gitkeep)

$ find /home/frank/workspace/blog/media/images -name "*.jpg" | wc -l
14
```

**Expected**:
```
media/images/
├── f3c25bd4-cc41-5e2f-9a68-20ed9b6d6f2f.jpg
├── f3c25bd4-cc41-5e2f-9a68-20ed9b6d6f2f.md  # ❌ Missing
├── 54516a64-9ba3-503f-ac1b-f0d2a251c7bc.jpg
└── 54516a64-9ba3-503f-ac1b-f0d2a251c7bc.md  # ❌ Missing
```

**Hypothesis**: Media enrichment .md files are being created but placed in wrong location (see Issue #3).

**Next Steps**:
- Verify all 14 images have enrichment .md files somewhere
- If they're in root (like 042aba52...), this confirms path issue
- If they're missing entirely, media enrichment may be failing silently

## Fixes Implemented

### ✅ IR_MESSAGE_SCHEMA Metadata for Enrichment Rows

**Problem**: Enrichment rows were missing required IR_MESSAGE_SCHEMA fields
**Fixed in**: PR #773, commit `e4da5613`

**Changes**:
- Updated `_create_enrichment_row()` to generate all 15 IR fields
- Modified `_enrich_urls()` to collect full IR metadata from source messages
- Modified `_extract_media_references()` to collect full IR metadata

**Fields now included**:
```python
{
    "event_id": uuid.uuid4(),                        # New UUID for enrichment
    "tenant_id": source["tenant_id"],                # Copied
    "source": source["source"],                      # Copied
    "thread_id": source["thread_id"],                # Link to thread
    "msg_id": f"enrichment-{event_id}",              # Generated
    "ts": timestamp + 1 microsecond,                 # Slightly after source
    "author_raw": "egregora",                        # System author
    "author_uuid": source["author_uuid"],            # Link to original author
    "text": "[enrichment content]",                   # Enrichment text
    "media_url": None,
    "media_type": None,
    "attrs": {"enrichment_type": type, "enrichment_id": id},
    "pii_flags": None,
    "created_at": source["created_at"],              # Copied for lineage
    "created_by_run": source["created_by_run"],      # Copied for lineage
}
```

**Result**: Enrichment rows now pass IR_MESSAGE_SCHEMA validation and maintain proper thread/author linkage.

## Root Cause Analysis

### Schema Transition Impact

The dev branch transitioned from CONVERSATION_SCHEMA to IR_MESSAGE_SCHEMA as the primary data format. This created several issues:

1. **Enrichment Stage** - Was using old schema column names (`.message`, `.timestamp`)
   - ✅ FIXED in PR #773

2. **Output Stage** - May have assumptions about schema structure
   - ⏳ INVESTIGATION NEEDED

3. **Document Routing** - OutputAdapter path resolution may not handle all DocumentTypes correctly
   - ⏳ INVESTIGATION NEEDED

### Potential Silent Failures

Several components have broad exception handlers that may be hiding issues:
- Journal saving (line 296-298 in agent.py): `except Exception`
- URL enrichment processing
- Media enrichment processing

**Recommendation**: Add structured logging before exception handlers to capture failure details.

## Next Investigation Steps

1. **Journal Entries**
   - [ ] Enable debug logging for `_save_journal_to_file()`
   - [ ] Check if intercalated_log is being populated
   - [ ] Verify OutputAdapter.serve() handles JOURNAL type
   - [ ] Check for template rendering errors in logs

2. **URL Enrichment Placeholders**
   - [ ] Inspect enrichment cache for affected URLs
   - [ ] Review Gemini API responses for patterns
   - [ ] Add validation for enrichment content quality

3. **Media Enrichment Paths**
   - [ ] Review MkDocsOutputAdapter.serve() for ENRICHMENT_MEDIA
   - [ ] Check url_convention.py path resolution
   - [ ] Verify expected vs actual directory structure
   - [ ] Document correct enrichment organization

4. **Missing Enrichment .md Files**
   - [ ] Search entire output for orphaned .md files
   - [ ] Verify enrichment creation vs serving pipeline
   - [ ] Check if media enrichments are being skipped

## Test Log References

- Full run log: `/tmp/egregora-full-run.log`
- Minimal test log: `/tmp/egregora-minimal-test.log`
- Enrichment fix log: `/tmp/egregora-enrichment-fix.log`

## Related PRs

- PR #773: Fix enrichment stage to use IR_MESSAGE_SCHEMA columns
- PR #772: Attempted message schema redesign (not merged)

---

**Last Updated**: 2025-11-15
**Investigator**: Claude (via Claude Code)
**Status**: Initial findings documented, investigation ongoing
