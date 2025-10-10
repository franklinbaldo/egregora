# Unicode Filename Hardcoding in WhatsApp Export Processing

## Problem

The `UnifiedProcessor._collect_sources()` method contains hardcoded filename handling that breaks when WhatsApp exports contain Unicode characters (particularly emojis) in filenames.

## Current Broken Code

```python
# In processor.py line ~224
chat_file = "Conversa do WhatsApp com Rationality Club LatAm ????.txt"
```

The actual filename contains an emoji: `"Conversa do WhatsApp com Rationality Club LatAm 🐀.txt"`

## Symptoms

- `KeyError: "There is no item named 'Conversa do WhatsApp com Rationality Club LatAm ????.txt' in the archive"`
- Processing fails when trying to access the chat file
- Unicode characters are displayed as question marks in hardcoded strings

## Temporary Fix Applied

```python
# Find the chat file (should be the .txt file)
txt_files = [f for f in zf.namelist() if f.endswith('.txt')]
if not txt_files:
    raise ValueError(f"No .txt file found in {zip_path}")
chat_file = txt_files[0]  # Use the first (and likely only) .txt file
```

## Root Cause Analysis

1. **Hardcoded Assumptions**: Code assumes specific filename format without accounting for Unicode
2. **Development vs Production**: Likely developed with ASCII-only test data
3. **Character Encoding**: Somewhere in the development chain, Unicode was corrupted to `????`

## Proper Solution Needed

1. **Dynamic Discovery**: Always discover files dynamically from ZIP contents
2. **Unicode Testing**: Add test cases with Unicode filenames
3. **Robust File Detection**: Use pattern matching instead of exact filenames
4. **Fallback Handling**: Handle cases where multiple or no `.txt` files exist

## Files Affected

- `src/egregora/processor.py` (lines ~220-235)
- Any other hardcoded filename references

## Impact

- **Severity**: High (complete processing failure)
- **Frequency**: Every real WhatsApp export with Unicode in group names
- **User Experience**: Cryptic error messages

## Testing Requirements

- Test with various Unicode characters (emojis, accented characters, CJK)
- Test with multiple `.txt` files in ZIP
- Test with no `.txt` files in ZIP
- Test with very long filenames

## Related Issues

This may be related to the broader issue of hardcoded group discovery vs dynamic discovery mentioned in the pruning process.