# Golden Test Fixtures Design

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

## Solution: Golden Test Fixtures

Create a system to:
1. **Record** API responses when running with real API keys
2. **Replay** those responses in tests without API calls
3. **Validate** that the pipeline produces expected outputs

## Architecture

### 1. Fixture Structure

```
tests/fixtures/golden/
├── api_responses/           # Mocked API responses
│   ├── embeddings/
│   │   ├── request_<hash>.json     # Request metadata
│   │   └── response_<hash>.json    # Response data
│   ├── generation/
│   │   ├── request_<hash>.json
│   │   └── response_<hash>.json
│   └── batch_jobs/
│       ├── job_<id>_status.json
│       └── job_<id>_result.json
└── expected_output/         # Expected pipeline outputs
    └── docs/               # Already captured!
        ├── posts/
        ├── profiles/
        └── media/
```

### 2. Recording Mode

Create a `GeminiClientRecorder` wrapper that:
- Intercepts all `genai.Client` calls
- Saves request/response pairs to `tests/fixtures/golden/api_responses/`
- Uses content hash to identify unique requests
- Saves batch job states and polling results

Usage:
```python
with GeminiClientRecorder(output_dir="tests/fixtures/golden/api_responses"):
    # Run pipeline - responses are recorded
    process_whatsapp_export(...)
```

### 3. Playback Mode

Create a `GeminiClientMock` that:
- Returns pre-recorded responses based on request content hash
- Simulates batch job lifecycle (PENDING → RUNNING → SUCCEEDED)
- Fails loudly if a request doesn't have a recorded response

Usage:
```python
@pytest.fixture
def gemini_client_mock():
    return GeminiClientMock(fixtures_dir="tests/fixtures/golden/api_responses")

def test_with_mocks(gemini_client_mock):
    # No API calls - uses fixtures
    process_whatsapp_export(..., client=gemini_client_mock)
```

### 4. Modified Tests

Transform `test_e2e_with_api.py` to:
- Use `GeminiClientMock` by default (fast, no API)
- Keep one `@pytest.mark.slow` test with real API for validation
- Add fixture comparison helpers

Example:
```python
def test_e2e_with_golden_fixtures(whatsapp_fixture, gemini_client_mock, tmp_path):
    """Fast test using pre-recorded API responses."""
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=tmp_path,
        client=gemini_client_mock,
        # ...
    )

    # Compare outputs with golden fixtures
    assert_posts_match_golden(tmp_path / "docs/posts", "tests/fixtures/golden/expected_output/docs/posts")

@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="Real API test")
def test_e2e_with_real_api_for_validation(whatsapp_fixture, gemini_api_key, tmp_path):
    """Occasional test with real API to validate fixtures are still accurate."""
    # Current test, but marked as slow
```

## Implementation Plan

### Phase 1: Mock Infrastructure (Jules - no API key needed)
- [ ] Create `GeminiClientMock` class that replays fixtures
- [ ] Add request hashing for fixture lookup
- [ ] Handle batch job state simulation (PENDING → RUNNING → SUCCEEDED)
- [ ] Create pytest fixtures for mock client
- [ ] Add output comparison helpers for golden files

### Phase 2: Test Refactoring (Jules - no API key needed)
- [ ] Refactor `test_e2e_with_api.py` to accept mock client
- [ ] Create new `test_with_golden_fixtures.py` using mocks
- [ ] Add output comparison against `tests/fixtures/golden/expected_output/`
- [ ] Keep one `@pytest.mark.slow` real API test in `test_e2e_with_api.py`
- [ ] Add documentation for test structure

### Phase 3: Recording Infrastructure (Jules - no API key needed)
- [ ] Create `GeminiClientRecorder` wrapper class
- [ ] Implement request/response serialization
- [ ] Add CLI script `scripts/record_golden_fixtures.py`
- [ ] Document how to regenerate fixtures (for humans with API keys)

### Phase 4: Record Actual Fixtures (Claude - REQUIRES API KEY)
- [ ] Run pipeline with `GeminiClientRecorder` enabled
- [ ] Capture all API responses to `tests/fixtures/golden/api_responses/`
- [ ] Verify mocked tests pass with recorded fixtures
- [ ] Commit API response fixtures

### Phase 5: CI/CD Integration (Jules)
- [ ] Update GitHub Actions to run mocked tests
- [ ] Add weekly job for real API validation (with secrets)
- [ ] Update testing documentation

## Benefits

- **Speed**: Tests run in seconds instead of minutes
- **Determinism**: Same inputs → same outputs
- **CI-friendly**: No API keys needed in CI
- **Cost**: Zero API costs for most test runs
- **Debugging**: Easier to debug with reproducible behavior

## Trade-offs

- **Maintenance**: Fixtures need updating when prompts/API changes
- **Storage**: Fixtures add ~1-5MB to repo
- **Coverage**: Need occasional real API tests to catch regressions

## References

- VCR.py pattern for HTTP mocking
- pytest-recording for similar approach
- Existing golden fixtures in `/tests/fixtures/golden/expected_output/`
