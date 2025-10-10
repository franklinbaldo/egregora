# Hardcoded Group Discovery After Pruning

## Problem

After the codebase pruning, automatic group discovery has been disabled and replaced with hardcoded group definitions in `UnifiedProcessor._collect_sources()`. This makes the system inflexible and breaks with different WhatsApp exports.

## Current Implementation

```python
# Hardcoded in processor.py ~220-240
zip_path = Path(self.config.zips_dir) / "real-whatsapp-export.zip"
if zip_path.exists():
    group_name = "Rationality Club LatAm"
    group_slug = "rationality-club-latam"
    # ... hardcoded values
```

## Issues

### 1. Inflexibility
- Only works with specifically named ZIP files
- Only handles one predefined group
- Cannot process arbitrary WhatsApp exports

### 2. Development vs Production Gap
- Works for development testing
- Breaks for real user scenarios
- No way to configure different groups via CLI

### 3. Missing Functionality
- No automatic group name detection from ZIP contents
- No support for multiple groups
- No fallback for unknown ZIP files

## Impact

- **User Experience**: Users cannot process their own exports without code changes
- **Scalability**: Cannot handle multiple different groups
- **Maintainability**: Requires code changes for each new group

## Root Cause

The pruning process removed `group_discovery.py` and the automatic discovery mechanisms, but left the hardcoded fallback as the only option.

## Possible Solutions

### Option 1: CLI-Based Group Configuration
Allow users to specify group information via CLI:
```bash
uv run egregora process \
  --group-name "My WhatsApp Group" \
  --group-slug "my-group" \
  --zip-file "my-export.zip"
```

### Option 2: Restore Limited Discovery
Implement basic group detection from ZIP metadata:
- Extract group name from chat file name
- Generate slug from group name
- Auto-detect export date

### Option 3: Configuration File Override
Allow group definitions in configuration:
```toml
[groups.my-group]
name = "My WhatsApp Group"
slug = "my-group"
zip_file = "my-export.zip"
```

### Option 4: Smart Defaults
Implement heuristics for common cases:
- Use ZIP filename for group name
- Auto-generate slugs
- Extract dates from file timestamps

## Recommended Approach

**Hybrid Solution**:
1. Implement basic discovery for common cases
2. Add CLI overrides for specific groups
3. Maintain current hardcoded fallback for development

## Files Affected

- `src/egregora/processor.py` (main hardcoded logic)
- `src/egregora/__main__.py` (CLI parameter additions)
- Configuration files (new group section)

## Testing Requirements

- Test with various ZIP filename formats
- Test with Unicode group names
- Test with multiple ZIP files
- Test CLI parameter combinations

## Priority

**Medium-High** - This is essential for real-world usage but has workarounds.

## Dependencies

- May require partial restoration of discovery logic
- CLI parameter additions
- Configuration schema changes