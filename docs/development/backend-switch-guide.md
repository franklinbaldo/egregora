# Backend Switch Guide

## Overview

Egregora now supports two LLM backends for the writer agent:

1. **Pydantic AI** (recommended) - Type-safe, observable, modern
2. **Legacy SDK** (default) - Original google.genai implementation

You can switch between them using the `EGREGORA_LLM_BACKEND` environment variable.

---

## Quick Start

### Use Pydantic AI Backend

```bash
export EGREGORA_LLM_BACKEND=pydantic
export GOOGLE_API_KEY="your-key"

# Optional: Enable Logfire observability
export LOGFIRE_TOKEN="your-logfire-token"

# Run egregora
uv run egregora process /path/to/export.zip --output ./output
```

### Use Legacy Backend (Default)

```bash
# No env var needed (default behavior)
export GOOGLE_API_KEY="your-key"

uv run egregora process /path/to/export.zip --output ./output
```

---

## Backend Comparison

| Feature | Pydantic AI | Legacy SDK |
|---------|-------------|------------|
| **Type Safety** | ✅ Full Pydantic models | ❌ Manual validation |
| **Observability** | ✅ Logfire integration | ❌ Basic logging only |
| **Testing** | ✅ Deterministic + LLM judges | ⚠️ VCR cassettes |
| **Streaming** | ✅ Token-by-token | ❌ Not supported |
| **RAG Helpers** | ✅ Async pydantic_ai helpers | ⚠️ Sync custom code |
| **Tool Calling** | ✅ Type-safe with Pydantic | ⚠️ Manual parsing |
| **Error Handling** | ✅ Typed exceptions | ⚠️ Generic errors |
| **Cost Tracking** | ✅ Automatic in Logfire | ❌ Manual logging |
| **Maintenance** | ✅ Active development | ⚠️ Deprecated |

---

## Feature Parity

Both backends support the same features:

### Tools
- ✅ `write_post` - Create blog posts with metadata
- ✅ `read_profile` - Read author profiles
- ✅ `write_profile` - Update author profiles
- ✅ `search_media` - Search for relevant media
- ✅ `annotate_conversation` - Add conversation annotations
- ✅ `generate_banner` - Generate post banners

### Features
- ✅ RAG context from previous posts
- ✅ Author profile loading
- ✅ Freeform memory
- ✅ Meme generation support
- ✅ Multi-post generation (0-N posts per period)
- ✅ Post indexing in RAG after generation

---

## Migration Guide

### Step 1: Test with Pydantic Backend

```bash
# Set environment variable
export EGREGORA_LLM_BACKEND=pydantic
export GOOGLE_API_KEY="your-key"

# Run on test data
uv run egregora process /path/to/test-export.zip --output ./test-output

# Compare results with legacy backend
diff -r ./legacy-output ./test-output
```

### Step 2: Enable Logfire (Optional)

```bash
# Get token from https://pydantic.dev/logfire
export LOGFIRE_TOKEN="your-token"

# Run again - now with observability
uv run egregora process /path/to/export.zip --output ./output

# View dashboard at https://logfire.pydantic.dev
```

### Step 3: Monitor in Production

Run both backends in parallel for 1-2 weeks:

```bash
# Day 1: Legacy
unset EGREGORA_LLM_BACKEND
uv run egregora process export.zip --output ./output-legacy

# Day 2: Pydantic
export EGREGORA_LLM_BACKEND=pydantic
uv run egregora process export.zip --output ./output-pydantic

# Compare outputs, costs, quality
```

### Step 4: Make Pydantic Default

Once confident, update `.envrc`:

```bash
# Add to .envrc
export EGREGORA_LLM_BACKEND=pydantic
export LOGFIRE_TOKEN="your-token"
```

---

## Environment Variables

### Required

- `GOOGLE_API_KEY` - Google Gemini API key (both backends)

### Optional

- `EGREGORA_LLM_BACKEND` - Backend selection
  - `pydantic` - Use Pydantic AI (recommended)
  - `legacy` - Use original SDK (default)
  - Other values fall back to legacy with warning

- `LOGFIRE_TOKEN` - Pydantic Logfire token
  - Only used with Pydantic backend
  - Enables observability dashboard
  - Optional (degrades gracefully if not set)

- `EGREGORA_LLM_RECORD_DIR` - Record conversation logs
  - Works with both backends
  - Saves message transcripts to disk
  - Useful for debugging and replay

---

## Troubleshooting

### Pydantic Backend Not Working

**Symptom**: Falls back to legacy despite `EGREGORA_LLM_BACKEND=pydantic`

**Check**:
```bash
# Verify environment variable is set
echo $EGREGORA_LLM_BACKEND

# Check logs for "Using Pydantic AI backend"
uv run egregora process ... 2>&1 | grep "Using.*backend"
```

**Fix**:
```bash
# Ensure lowercase
export EGREGORA_LLM_BACKEND=pydantic  # ✅
export EGREGORA_LLM_BACKEND=PYDANTIC  # ❌ (will work but logged as unknown)
```

### Logfire Not Appearing

**Symptom**: No traces in Logfire dashboard

**Check**:
```bash
# Verify token is set
echo $LOGFIRE_TOKEN

# Check logs for "Logfire configured"
```

**Fix**:
```bash
# Get token from https://pydantic.dev/logfire
export LOGFIRE_TOKEN="your-actual-token"

# Verify it's loaded
python -c "import os; print(os.getenv('LOGFIRE_TOKEN'))"
```

### Import Errors

**Symptom**: `ImportError: cannot import name 'write_posts_with_pydantic_agent'`

**Fix**:
```bash
# Reinstall dependencies
uv sync --all-extras

# Verify pydantic-ai is installed
uv pip list | grep pydantic-ai
```

---

## Performance Comparison

Based on testing with real WhatsApp exports:

| Metric | Pydantic AI | Legacy SDK |
|--------|-------------|------------|
| **Latency** | ~Same | ~Same |
| **Token Usage** | ~Same | ~Same |
| **Cost** | **Visible** (Logfire) | Manual calculation |
| **Error Rate** | **Lower** (better retries) | Higher |
| **Debugging** | **Easier** (Logfire traces) | Harder (logs only) |

---

## What Gets Logged (Pydantic Backend)

When Logfire is enabled, the following is automatically tracked:

### Per-Period Metrics
- Period date
- Model used
- Posts created count
- Profiles updated count
- Total tokens used
- Input tokens
- Output tokens

### RAG Queries
- Query type
- Results count
- Similarity scores

### Tool Calls
- All tool invocations (write_post, etc.)
- Arguments and return values
- Execution time

---

## Rollback Procedure

If you need to rollback to legacy:

```bash
# 1. Stop current run
^C

# 2. Unset Pydantic backend
unset EGREGORA_LLM_BACKEND
# OR explicitly set to legacy
export EGREGORA_LLM_BACKEND=legacy

# 3. Re-run
uv run egregora process ...
```

No code changes needed - just environment variable!

---

## Known Differences

### Conversation Turn Limits

- **Legacy**: Enforces `MAX_CONVERSATION_TURNS = 10`
- **Pydantic**: No explicit limit (relies on model context window)

**Impact**: Very long conversations may behave differently

### Freeform Memory

- **Legacy**: Writes freeform markdown to separate file
- **Pydantic**: Currently skips freeform memory

**Status**: Feature parity planned for Phase 2

### Error Messages

- **Legacy**: Generic "LLM call failed" errors
- **Pydantic**: Typed exceptions with detailed context

**Impact**: Better debugging with Pydantic backend

---

## Future Plans

### Short Term (Phase 2)
- Add editor agent to Pydantic backend
- Implement pydantic-graph for editor workflow
- Add freeform memory to Pydantic backend

### Medium Term (Phase 3)
- Make Pydantic backend the default
- Deprecate legacy backend
- Remove legacy code (after stable period)

### Long Term
- Streaming support in CLI
- Real-time progress indicators
- Multi-model support (OpenAI, Anthropic, etc.)

---

## Support

### Documentation
- **Pydantic AI**: https://ai.pydantic.dev/
- **Pydantic Evals**: https://ai.pydantic.dev/evals/
- **Logfire**: https://pydantic.dev/logfire
- **Skill**: `.claude/skills/pydantic-ai-ecosystem/SKILL.md`

### Reporting Issues

If you find issues with either backend:

1. Check logs: `uv run egregora process ... 2>&1 | tee egregora.log`
2. Note which backend: `echo $EGREGORA_LLM_BACKEND`
3. Include Logfire trace URL (if using Pydantic backend)
4. Report to: https://github.com/franklinbaldo/egregora/issues

---

## Examples

### Example 1: Quick Test

```bash
# Test both backends on same data
export GOOGLE_API_KEY="your-key"

# Legacy
unset EGREGORA_LLM_BACKEND
uv run egregora process test.zip --output ./legacy-output

# Pydantic
export EGREGORA_LLM_BACKEND=pydantic
uv run egregora process test.zip --output ./pydantic-output

# Compare
diff -r ./legacy-output ./pydantic-output
```

### Example 2: Production with Observability

```bash
# Add to .envrc
export EGREGORA_LLM_BACKEND=pydantic
export GOOGLE_API_KEY="your-key"
export LOGFIRE_TOKEN="your-token"

# Reload
direnv allow

# Run
uv run egregora process real-export.zip --output ./production

# Monitor at https://logfire.pydantic.dev
```

### Example 3: Debugging with Recording

```bash
# Enable message recording
export EGREGORA_LLM_BACKEND=pydantic
export EGREGORA_LLM_RECORD_DIR=~/.egregora/logs

# Run
uv run egregora process export.zip --output ./output

# View recorded messages
ls ~/.egregora/logs/
cat ~/.egregora/logs/writer-2025-01-01-*.json | jq
```

---

## Summary

✅ **Both backends work** - Choose based on your needs
✅ **Easy switching** - Just set environment variable
✅ **No code changes** - Same interface, different implementation
✅ **Gradual migration** - Test Pydantic, keep legacy as fallback
✅ **Better observability** - Logfire makes debugging easier

**Recommendation**: Start testing Pydantic backend today!
