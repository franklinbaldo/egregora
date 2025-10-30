# Gemini API Setup Investigation

## Issue Summary

When attempting to run egregora with the provided `GEMINI_API_KEY`, the pipeline fails with 403 Forbidden errors:

```
HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent "HTTP/1.1 403 Forbidden"
```

## Root Cause

After investigation, I discovered that:

1. **The provided API keys are not real**:
   - `GEMINI_API_KEY="AIzaSyAa0KiCkrBLKwblc1SnNlpRf3ohQnK4uic"` - This is an example/test key without actual permissions
   - `JULES_API_KEY` - Also returns 403 Forbidden, suggesting it's also a test key

2. **Test Infrastructure Uses Mocks**:
   - The test suite in `tests/conftest.py` (lines 32-106) creates stub/mock implementations of the Google genai modules
   - The fixture `gemini_api_key()` returns `"test-key"` for unit tests
   - E2E tests that require real API calls use `REAL_GEMINI_API_KEY` environment variable instead (see `tests/test_e2e_with_api.py:26`)

3. **Evidence**:
   ```python
   # From tests/test_e2e_with_api.py
   pytestmark = pytest.mark.skipif(
       not os.getenv("REAL_GEMINI_API_KEY"),
       reason="REAL_GEMINI_API_KEY environment variable not set - skipping E2E tests with real API",
   )
   ```

## Solution

To successfully run egregora with the Gemini API, you need:

### 1. Obtain a Valid Google API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create a new API key
4. Ensure the key has access to:
   - Gemini API (generativelanguage.googleapis.com)
   - File upload capabilities
   - Content generation endpoints

### 2. Set the Environment Variable

Export the **real** API key:

```bash
export GOOGLE_API_KEY="your-actual-api-key-here"
# OR
export REAL_GEMINI_API_KEY="your-actual-api-key-here"
```

### 3. Run Egregora

```bash
# With enrichment (requires file upload permissions)
egregora process "tests/Conversa do WhatsApp com Teste.zip" --output=test-output --period=day

# Without enrichment
egregora process "tests/Conversa do WhatsApp com Teste.zip" --output=test-output --period=day --no-enable-enrichment
```

### 4. Verify Installation

The pipeline was successfully installed with Python 3.12:

```bash
# Installation command that worked:
python3.12 -m pip install -e . --break-system-packages --ignore-installed PyYAML

# Command is available:
egregora --help
```

## Test Results

### What Works ✅

- Package installation with Python 3.12
- CLI command registration
- WhatsApp export parsing
- MkDocs scaffold initialization
- Message grouping by period
- Profile discovery

### What Requires Valid API Key ❌

- Content generation (`generateContent` endpoint)
- File uploads for enrichment
- Embedding generation for RAG
- All LLM-powered features

## Additional Notes

1. **Python Version**: The project requires Python >= 3.12. Python 3.11 will not work.

2. **DuckDB VSS Extension**: There's a warning about downloading the VSS extension:
   ```
   Failed to download extension "vss" at URL http://extensions.duckdb.org/...
   ```
   This is likely a network connectivity issue and not related to the API key problem.

3. **API Endpoints Used**:
   - Content generation: `/v1beta/models/gemini-flash-latest:generateContent`
   - File upload: `/upload/v1beta/files`
   - Embeddings: `/v1beta/models/gemini-embedding-001`

## Recommendation

**To test egregora with real API calls**, you need to:

1. Obtain a valid Google Gemini API key from Google AI Studio
2. Set it as `GOOGLE_API_KEY` or `REAL_GEMINI_API_KEY`
3. Ensure the key has proper permissions for the Generative Language API
4. Be aware that API calls will incur costs based on Google's pricing

The example API key provided (`AIzaSyAa0KiCkrBLKwblc1SnNlpRf3ohQnK4uic`) is intentionally non-functional and meant for documentation/testing purposes only.
