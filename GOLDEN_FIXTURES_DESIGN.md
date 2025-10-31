# Golden Test Fixtures Design (pytest-vcr)

## Problem Statement

E2E tests with real API calls (`test_e2e_with_api.py`) are:
- **Very slow** (~2-5 minutes for 10 messages) due to async batch API calls
- **Expensive** (consuming API quota)
- **Non-deterministic** (LLM responses vary)
- **Not suitable for CI/CD**

Even with `--no-enable-enrichment`, the system still makes multiple batch API calls for:
1. Embeddings for RAG similarity search
2. Post generation
3. Profile generation
4. Post indexing

## Solution: pytest-vcr

We use **pytest-vcr** (VCR.py for pytest) to record and replay HTTP interactions with the Gemini API. This is the industry-standard approach for testing code that makes HTTP requests.

### Why pytest-vcr?

- **Industry standard**: VCR.py pattern is widely used across languages
- **Automatic**: Records all HTTP interactions transparently
- **Well-maintained**: Active community and regular updates
- **Secure**: Built-in filtering for sensitive data (API keys, auth tokens)
- **Simple**: Just add a decorator to tests
- **Flexible**: Multiple record modes (once, new_episodes, all, none)

## Architecture

### 1. Cassette Storage

```
tests/fixtures/vcr_cassettes/
├── test_with_golden_fixtures/
│   └── test_pipeline_with_vcr_fixtures.yaml  # Recorded HTTP interactions
└── ... (other test cassettes)
```

Cassettes are YAML files that contain:
- HTTP request details (method, URL, headers, body)
- HTTP response details (status, headers, body)
- Automatically filtered to remove API keys

### 2. Configuration

**In `pyproject.toml`:**
```toml
[tool.pytest.ini_options]
vcr_record_mode = "once"  # Record once, then replay
vcr_cassette_dir = "tests/fixtures/vcr_cassettes"
```

**In `tests/conftest.py`:**
```python
@pytest.fixture(scope="module")
def vcr_config():
    """VCR configuration with API key filtering."""
    return {
        "record_mode": "once",
        "filter_headers": [
            ("x-goog-api-key", "DUMMY_API_KEY"),
            ("authorization", "DUMMY_AUTH"),
        ],
        "filter_query_parameters": [
            ("key", "DUMMY_API_KEY"),
        ],
        "match_on": ["method", "scheme", "host", "port", "path", "body"],
    }
```

### 3. Recording Workflow

**To record new cassettes (requires GOOGLE_API_KEY):**

```bash
# Set your API key
export GOOGLE_API_KEY="your-actual-api-key"

# Delete old cassettes (if regenerating)
rm -rf tests/fixtures/vcr_cassettes/test_with_golden_fixtures/

# Record new cassettes
pytest tests/test_with_golden_fixtures.py --vcr-record=all
```

This will:
1. Run the test with real API calls
2. Record all HTTP interactions to cassette files
3. Filter out sensitive data (API keys)
4. Save cassettes to `tests/fixtures/vcr_cassettes/`

### 4. Playback Workflow

**To use existing cassettes (default):**

```bash
# No API key needed!
pytest tests/test_with_golden_fixtures.py
```

When tests run:
1. pytest-vcr intercepts HTTP requests
2. Matches requests against recorded cassettes
3. Returns recorded responses instantly
4. No actual API calls are made

### 5. Writing Tests with VCR

**Example test:**

```python
import pytest
import os
from google import genai

@pytest.mark.vcr
@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="API key required for recording"
)
def test_pipeline_with_vcr_fixtures(whatsapp_fixture, tmp_path):
    """Test using VCR-recorded API responses."""
    # Create a real Gemini client
    # VCR will intercept the HTTP calls
    api_key = os.getenv("GOOGLE_API_KEY", "dummy-key-for-replay")
    client = genai.Client(api_key=api_key)

    # Run the pipeline
    # VCR records/replays HTTP interactions automatically
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        client=client,  # Real client, but VCR intercepts
    )

    # Assertions...
```

The `@pytest.mark.vcr` decorator automatically:
- Records HTTP interactions on first run
- Replays from cassettes on subsequent runs
- Applies filters from `vcr_config` fixture

### 6. Regenerating Cassettes

**When to regenerate:**
- You change prompts or request parameters
- You upgrade the Gemini API client library
- You add new API calls to the pipeline
- Cassettes become outdated

**How to regenerate:**

```bash
# 1. Delete old cassettes
rm -rf tests/fixtures/vcr_cassettes/test_with_golden_fixtures/

# 2. Set API key
export GOOGLE_API_KEY="your-actual-api-key"

# 3. Re-record
pytest tests/test_with_golden_fixtures.py --vcr-record=all

# 4. Verify cassettes were created
ls -la tests/fixtures/vcr_cassettes/test_with_golden_fixtures/

# 5. Commit new cassettes
git add tests/fixtures/vcr_cassettes/
git commit -m "chore: regenerate VCR cassettes"
```

## VCR Record Modes

pytest-vcr supports different record modes:

- **`once`** (default): Record once, error if cassette missing
- **`new_episodes`**: Record new interactions, replay existing
- **`all`**: Always make real requests and update cassettes
- **`none`**: Always use cassettes, error if missing

Set via:
```bash
pytest --vcr-record=<mode>
```

## Benefits

- **Speed**: Tests run in seconds instead of minutes
- **Determinism**: Same inputs → same outputs (HTTP-level replay)
- **CI-friendly**: No API keys needed in CI
- **Cost**: Zero API costs for replayed tests
- **Debugging**: Easier to debug with reproducible behavior
- **Standard**: Uses industry-standard VCR.py pattern
- **Security**: Automatic filtering of sensitive data
- **Maintenance**: Well-maintained by active community

## Trade-offs

- **Cassette size**: YAML files can be large for complex responses
- **Maintenance**: Cassettes need updating when API changes
- **Coverage**: Still need occasional real API tests for validation
- **Binary data**: Large binary responses increase repo size
- **HTTP-level**: Records at HTTP level, not at SDK method level

## Comparison with Custom Implementation

| Feature | Custom Playback | pytest-vcr |
|---------|----------------|------------|
| Implementation | Custom code to maintain | Standard library |
| Recording level | SDK methods | HTTP requests |
| Maintenance | Manual updates needed | Community maintained |
| Filtering | Manual implementation | Built-in |
| Flexibility | High (custom logic) | High (configurable) |
| Learning curve | Codebase-specific | Standard pattern |
| File format | Custom JSON | Standard YAML |

## Best Practices

1. **Commit cassettes**: Check cassettes into version control
2. **Filter secrets**: Always filter API keys and tokens
3. **Document regeneration**: Note when/why cassettes were updated
4. **Regular updates**: Periodically run with real API to validate
5. **Small cassettes**: Keep tests focused to reduce cassette size
6. **CI/CD**: Run with cassettes in CI, real API in scheduled jobs
7. **Review changes**: Review cassette diffs when regenerating

## Related Files

- `pyproject.toml`: pytest-vcr configuration
- `tests/conftest.py`: VCR fixture with filtering
- `tests/test_with_golden_fixtures.py`: Example test using VCR
- `tests/fixtures/vcr_cassettes/`: Recorded cassettes

## References

- [VCR.py documentation](https://vcrpy.readthedocs.io/)
- [pytest-vcr documentation](https://pytest-vcr.readthedocs.io/)
- [VCR pattern origin (Ruby)](https://github.com/vcr/vcr)
