# --disable-enrichment Flag Not Fully Effective

## Problem

The `--disable-enrichment` CLI flag does not prevent all API calls to Gemini. Even with enrichment disabled, the core post generation still requires API access, making it impossible to run the pipeline offline or without API quotas.

## Expected Behavior

When `--disable-enrichment` is specified, users expect:
- No external API calls for link/media enrichment
- Ability to generate basic posts without API access
- Offline processing capability

## Actual Behavior

Even with `--disable-enrichment`:
- Core post generation still calls Gemini API
- Pipeline fails without valid API key
- No offline mode available

## Analysis

### What --disable-enrichment Currently Does
- Disables link analysis and media enrichment
- Reduces external API calls
- Prevents enrichment cache generation

### What It Doesn't Do
- Core post generation still requires Gemini API
- System prompts and message processing use LLM
- No fallback for offline post generation

## Root Cause

The flag only disables the enrichment subsystem, but post generation (`PostGenerator`) always requires API access for:
- System instruction processing
- Message summarization
- Post content generation

## User Confusion

Users reasonably expect that "disable enrichment" means:
1. No external dependencies
2. Basic functionality without API
3. Offline processing capability

But the current implementation treats enrichment as just one of many LLM features.

## Proposed Solutions

### Option 1: True Offline Mode
Add `--offline` flag that:
- Disables all external API calls
- Uses template-based post generation
- Provides basic formatting without LLM processing

### Option 2: Clarify Flag Purpose
Rename to `--disable-link-enrichment` and add:
- `--offline` for full offline mode
- `--basic-posts` for template-only generation
- Clear documentation about API requirements

### Option 3: Fallback Templates
When API is unavailable:
- Fall back to simple template-based posts
- Include raw transcripts with basic formatting
- Warn user about reduced functionality

## Implementation Challenges

### Template-Based Generation
```python
def generate_basic_post(transcripts, config):
    """Generate post without LLM using templates."""
    return f"""
# {config.group_name} - {date}

## Messages ({len(transcripts)} lines)

{format_transcripts(transcripts)}

*Generated offline by Egregora*
"""
```

### API Detection
```python
def has_api_access():
    try:
        # Quick API test
        return test_gemini_connection()
    except:
        return False
```

## Files Affected

- `src/egregora/generator.py` (core generation logic)
- `src/egregora/__main__.py` (CLI flags and options)
- `src/egregora/processor.py` (flow control)
- Template files (new offline templates)

## User Impact

### Current Confusion
- Users expect offline capability
- Flag name is misleading
- No workaround for API issues

### After Fix
- Clear separation of features
- Offline processing option
- Graceful degradation

## Priority

**Medium** - Important for user experience and setting proper expectations.

## Testing Requirements

- Test offline mode without API key
- Test graceful degradation when API fails
- Test template-based post quality
- Test flag behavior combinations

## Documentation Needs

- Clear explanation of API requirements
- Offline mode limitations
- Feature comparison table