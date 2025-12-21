# Fix SDK Warnings: "Both GOOGLE_API_KEY and GEMINI_API_KEY are set"

## Problem

The google-genai SDK emits warnings every time `genai.Client()` is instantiated when both `GOOGLE_API_KEY` and `GEMINI_API_KEY` environment variables are set:

```
WARNING  Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.
```

This warning appears 15-20 times during pipeline runs, especially during:

1. Taxonomy generation (creates fallback model with multiple clients)
2. API key validation
3. Embedding and enrichment operations

## Current Partial Fix

A `dedupe_api_keys()` function was added to `egregora/utils/env.py` that unsets `GEMINI_API_KEY` when `GOOGLE_API_KEY` is also present:

```python
def dedupe_api_keys() -> None:
    """Remove duplicate API key environment variables."""
    google_key = os.environ.get("GOOGLE_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if google_key and gemini_key:
        os.environ.pop("GEMINI_API_KEY", None)
```

This is called:

- At package import time in `egregora/__init__.py`
- At pipeline startup in `write.py`

**Issue:** The SDK is imported and clients are created in places that execute before `dedupe_api_keys()` runs, particularly in the fallback model creation.

## Root Cause

The `create_fallback_model()` function in `egregora/utils/model_fallback.py` creates multiple `genai.Client()` instances for each API key when building the fallback chain. Since this happens inside a library that may import before the dedupe runs, the warnings still appear.

## Proposed Solution

1. **Option A (Simpler):** Move the `dedupe_api_keys()` call to even earlier - potentially as a side effect of importing `env.py` itself (not just when egregora package is imported).

2. **Option B (More robust):** Wrap all `genai.Client()` calls with a helper that suppresses the specific warning:

```python
import warnings

def create_genai_client(**kwargs):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Both GOOGLE_API_KEY and GEMINI_API_KEY")
        return genai.Client(**kwargs)
```

Then replace all `genai.Client()` calls in the codebase with `create_genai_client()`.

## Files to Modify

- `egregora/utils/model_fallback.py` - Uses `genai.Client()` in fallback model creation
- `egregora/agents/enricher.py` - Multiple `genai.Client()` instantiations
- `egregora/orchestration/factory.py` - `create_gemini_client()`
- `egregora/orchestration/pipelines/write.py` - `_create_gemini_client()`

## Acceptance Criteria

- [ ] No "Both GOOGLE_API_KEY and GEMINI_API_KEY" warnings appear in pipeline logs
- [ ] All existing tests pass
- [ ] No breaking changes to API key handling
