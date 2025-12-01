# OpenRouter Integration & Unlimited Generation

## Overview
Integrated OpenRouter API with pydantic-ai's native support to enable unlimited blog generation by automatically falling back to dozens of free models when Google API quotas are exhausted.

## Key Features

### 1. Dynamic Free Model Discovery
- Automatically fetches all free OpenRouter models via their API
- Caches results for 1 hour to avoid rate limiting
- Falls back to hardcoded list if API is unavailable
- Located in: `src/egregora/utils/model_fallback.py`

### 2. Native Pydantic-AI FallbackModel
- Replaced 100+ lines of custom fallback logic
- Uses pydantic-ai's built-in `FallbackModel` class
- Automatically handles `ModelAPIError` (includes 429 and other API errors)
- Simplified API: `create_fallback_model(primary_model, include_openrouter=True)`

### 3. Fallback Priority Order
1. **Google Gemini models** (in order):
   - `gemini-2.5-pro`
   - `gemini-2.5-flash`
   - `gemini-2.0-flash`
   - `gemini-2.5-flash-lite`
2. **OpenRouter free models** (dynamically fetched):
   - All models with $0.00 pricing for both prompt and completion
   - Examples: grok-beta, gemma-2-9b-it:free, llama-3.1-8b-instruct:free, etc.

### 4. Rate Limiting & Concurrency Control
- Added `max_concurrent_enrichments` config (default: 5)
- Uses asyncio Semaphore to limit concurrent requests
- Prevents hitting rate limits during parallel processing
- Configurable in `.egregora/config.yml`:
  ```yaml
  enrichment:
    max_concurrent_enrichments: 5  # Adjust based on API limits
  ```

## Files Modified

### Core Changes
1. **`src/egregora/utils/model_fallback.py`** - New fallback utility
   - `get_openrouter_free_models()` - Fetch free models from API
   - `create_fallback_model()` - Create FallbackModel with OpenRouter support
   - Caching mechanism for API responses

2. **`src/egregora/config/settings.py`**
   - Added `get_openrouter_api_key()` helper
   - Added `openrouter_api_key_status()` helper
   - Added `max_concurrent_enrichments` to `EnrichmentSettings`

3. **`src/egregora/agents/writer.py`**
   - Simplified from 60+ lines to ~20 lines
   - Uses `create_fallback_model()` instead of custom logic
   - Automatically includes all OpenRouter free models

4. **`src/egregora/agents/reader/agent.py`**
   - Simplified fallback implementation
   - Uses `create_fallback_model()`
   - Fixed `result_type` → `output_type` for pydantic-ai compatibility

5. **`src/egregora/orchestration/workers.py`**
   - Removed complex batch API processing
   - Simplified to standard pydantic-ai agents
   - Added concurrent processing with semaphore-based rate limiting
   - Fixed `result_type` → `output_type`

6. **`/home/frank/workspace/.envrc`**
   - Fixed `OPENROUTER_API_KEY` export syntax (removed spaces around =)

## Configuration

### Environment Variables
```bash
export GOOGLE_API_KEY="your-google-api-key"
export OPENROUTER_API_KEY="your-openrouter-api-key"
```

### Config File (.egregora/config.yml)
```yaml
enrichment:
  enabled: true
  max_enrichments: 50
  max_concurrent_enrichments: 5  # NEW: Control concurrent requests
```

## Benefits

✅ **Unlimited Generation**: When Google APIs hit 429 quota limits, automatically switches to OpenRouter free models  
✅ **Simpler Code**: Removed 100+ lines of custom fallback logic  
✅ **Dynamic Discovery**: Always up-to-date with new free models  
✅ **Better Error Handling**: Falls back on any API error, not just 429  
✅ **Rate Limiting**: Configurable concurrency prevents hitting API limits  
✅ **Zero Cost**: All OpenRouter fallback models are 100% free  

## Usage Example

```python
from egregora.utils.model_fallback import create_fallback_model
from pydantic_ai import Agent

# Create model with automatic fallback to OpenRouter free models
model = create_fallback_model("google-gla:gemini-2.0-flash")

# Use in agent - will automatically fall back on API errors
agent = Agent(model=model, output_type=MyOutputType)
result = await agent.run("Your prompt")
```

## Testing

The changes are currently being tested with:
```bash
rm -rf /home/frank/workspace/blog-test && \
source /home/frank/workspace/.envrc && \
uv run egregora write /home/frank/workspace/real-whatsapp-export.zip \
  --output-dir /home/frank/workspace/blog-test \
  --max-windows 1
```

## Next Steps

1. Monitor blog generation completion
2. Verify fallback works when Google quota is exhausted
3. Fine-tune `max_concurrent_enrichments` based on rate limits
4. Consider adding per-model rate limit configuration
5. Add metrics/logging for fallback usage
