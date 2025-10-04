# Flexible ZIP Naming - Design Plan

## Problem Statement

Currently, users must manually rename WhatsApp export files to include dates in YYYY-MM-DD format:
- **Current requirement**: `2025-10-03-Conversa do WhatsApp com Rationality Club LatAm.zip`
- **Natural WhatsApp export**: `Conversa do WhatsApp com Rationality Club LatAm 🐀.zip`

This creates poor UX because:
1. Manual renaming is tedious and error-prone
2. Users may not understand the date requirement immediately
3. The system already supports multiple date extraction strategies
4. Multiple exports from the same group require distinct filenames

## Current Date Extraction Logic

The system already handles date extraction in `src/egregora/group_discovery.py:_extract_date()`:

```python
def _extract_date(zip_path: Path, zf: zipfile.ZipFile, chat_file: str) -> date:
    """Extract date from export (ZIP name > content > mtime)."""

    # 1. Try ZIP filename (e.g., "2025-10-03-group.zip")
    match = re.search(r"(\d{4}-\d{2}-\d{2})", zip_path.name)
    if match:
        return date.fromisoformat(match.group(1))

    # 2. Try parsing first 20 lines of chat content
    # 3. Fallback to file modification time
```

**This already works!** The issue is that users don't know they can omit dates.

## Proposed Solution

### Phase 1: Documentation & UX Improvements (No Code Changes)

**Goal**: Make it clear that date-in-filename is optional.

1. **Update README.md** - Clarify that dates are optional:
   ```markdown
   ## Step 4: Prepare WhatsApp Exports

   1. Export your WhatsApp conversation as a `.zip` file
   2. Place it in `data/whatsapp_zips/`
   3. **Optional**: Rename with date prefix `YYYY-MM-DD-` for explicit control

   Examples:
   - ✅ `Conversa do WhatsApp com My Group.zip` (auto-detects date)
   - ✅ `2025-10-03-My Group.zip` (explicit date)
   - ✅ `WhatsApp Chat with Team.zip` (auto-detects date)
   ```

2. **Add docs/zip-naming.md** - Comprehensive guide on naming strategies:
   - Auto-detection behavior
   - When to use explicit dates
   - Handling multiple exports
   - Troubleshooting date detection

3. **Improve CLI warnings** - When date detection falls back to mtime:
   ```python
   logger.warning(
       "ZIP '%s': Date extracted from file mtime (%s). "
       "Consider renaming to 'YYYY-MM-DD-%s' for explicit control.",
       zip_path.name,
       parsed_date,
       zip_path.name
   )
   ```

### Phase 2: Enhanced Date Detection (Code Improvements)

**Goal**: Make auto-detection more robust.

1. **Extract date from ZIP internal paths** - Check media filenames:
   ```python
   # WhatsApp media often has timestamps: IMG-20251003-WA0001.jpg
   for media_file in media_files:
       match = re.search(r"(\d{8})", media_file)  # YYYYMMDD
       if match:
           return parse_date_yyyymmdd(match.group(1))
   ```

2. **Parse more message formats** - Support international date formats:
   ```python
   # Current: US format only
   # Enhanced: Support DD/MM/YYYY, YYYY-MM-DD in messages
   ```

3. **Validate detected dates** - Warn if detected date seems incorrect:
   ```python
   if detected_date > datetime.now().date():
       logger.warning("Detected future date %s - using file mtime instead", detected_date)
   ```

### Phase 3: Collision Handling (Multiple Exports)

**Goal**: Support multiple exports from same group on same date.

Currently, if multiple exports exist:
- They're grouped by `group_slug`
- Sorted by `export_date`
- Merged/deduped at message level

**This already works!** The system merges:
```python
# src/egregora/transcript.py
def load_source_dataframe(source: GroupSource) -> pl.DataFrame:
    """Load and merge all exports for a group."""
    # Automatically deduplicates messages
```

**What needs clarification**:
- Document that duplicates are automatically handled
- Add example showing multiple exports:
  ```
  data/whatsapp_zips/
    ├── Conversa do WhatsApp com Team.zip         # Export from 2025-10-01
    ├── 2025-10-03-Team.zip                       # Export from 2025-10-03
    └── Conversa do WhatsApp com Team (1).zip     # Another export
  ```

### Phase 4: Advanced Features (Future)

1. **Smart export grouping**
   - Detect when ZIP name has `(1)`, `(2)` suffixes (browser downloads)
   - Automatically associate with parent group

2. **Date range detection**
   - Parse first and last message dates
   - Use range for better organization: `2025-09-01_to_2025-10-01`

3. **Interactive rename helper**
   ```bash
   uv run egregora rename-zips
   # Scans zips_dir, suggests renames based on detected dates
   ```

## Implementation Checklist

### Phase 1 (Documentation) - Immediate

- [ ] Update README.md "Prepare WhatsApp Exports" section
- [ ] Create docs/zip-naming.md with comprehensive guide
- [ ] Add examples to ENRICHMENT_QUICKSTART.md
- [ ] Update CLI help text for `--zips-dir` option
- [ ] Add warning message when falling back to mtime

### Phase 2 (Robustness) - Short term

- [ ] Extract dates from media filenames (IMG-YYYYMMDD-*)
- [ ] Support more date formats in message parsing
- [ ] Add date validation (reject future dates)
- [ ] Log detection strategy used (filename/content/mtime)

### Phase 3 (Clarity) - Short term

- [ ] Document deduplication behavior in docs/
- [ ] Add tests for multiple exports from same group
- [ ] Show export count in `--list` output
- [ ] Add example with multiple exports to README

### Phase 4 (Advanced) - Future

- [ ] Smart grouping for browser download suffixes
- [ ] Date range extraction from message content
- [ ] Interactive rename command
- [ ] Export metadata cache to avoid re-scanning

## Migration Path

**No breaking changes!** All existing workflows continue to work:

1. Old workflow (explicit dates): ✅ Still works
2. New workflow (auto-detect): ✅ Already works, just needs documentation
3. Mixed workflow: ✅ Works (some with dates, some without)

## Testing Strategy

### Current Behavior Tests

```python
def test_date_extraction_from_filename():
    """Verify YYYY-MM-DD in filename is detected."""

def test_date_extraction_from_content():
    """Verify dates are parsed from message timestamps."""

def test_date_extraction_fallback_mtime():
    """Verify mtime is used when other methods fail."""
```

### New Tests Needed

```python
def test_natural_whatsapp_export_names():
    """Test with unmodified WhatsApp export names."""
    # "Conversa do WhatsApp com Group.zip" should work

def test_multiple_exports_same_group():
    """Multiple exports from same group are merged."""

def test_date_extraction_warning_on_mtime():
    """Warning logged when falling back to mtime."""

def test_media_filename_date_detection():
    """Extract date from IMG-20251003-WA0001.jpg patterns."""
```

## Success Metrics

1. **Zero required renames** - Users can use raw WhatsApp exports
2. **Clear feedback** - Logs show which detection method was used
3. **Predictable behavior** - Explicit dates always override auto-detection
4. **Good defaults** - Auto-detection works for 95%+ of exports

## References

- Current implementation: `src/egregora/group_discovery.py`
- Date parsing: `src/egregora/date_utils.py`
- Merge logic: `src/egregora/merger.py`
- Transcript loading: `src/egregora/transcript.py`

## Questions for User

1. Should we warn/error if multiple exports have same detected date?
2. Prefer browser suffixes `(1)`, `(2)` or timestamp-based `_001`, `_002`?
3. Should `--list` command show detected vs. explicit dates differently?
