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
│   │   └── response_<hash>.json    # Request and response data
│   └── generation/
│       └── response_<hash>.json
└── expected_output/         # Expected pipeline outputs
    └── docs/
        ├── posts/
        ├── profiles/
        └── media/
```
Each `response_<hash>.json` file contains both the original request and the corresponding response.

### 2. Recording Workflow

A `GeminiClientRecorder` wrapper intercepts all `genai.Client` calls. It saves request/response pairs to `tests/fixtures/golden/api_responses/`.

**To record new fixtures:**

Use the `scripts/record_golden_fixtures.py` script. This script runs the main pipeline with the recorder enabled.

```bash
uv run python scripts/record_golden_fixtures.py \
  --zip-path "tests/Conversa do WhatsApp com Teste.zip" \
  --output-dir /tmp/test_site \
  --fixtures-dir tests/fixtures/golden/api_responses
```

This will populate the `tests/fixtures/golden/api_responses` directory with new fixtures based on the API calls made during the pipeline run.

### 3. Playback Workflow

The `GeminiClientPlayback` class is used in tests to replay the recorded fixtures.

- It loads all fixtures from the `tests/fixtures/golden/api_responses` directory into memory.
- When a method like `embed_content` or `generate_content` is called, it hashes the request arguments.
- It looks up the response corresponding to the request hash and returns it.
- This allows tests to run without making any live API calls.

**How tests use playback:**

A `playback_client` fixture is available in `tests/conftest.py`. Tests can use this fixture to get an instance of `GeminiClientPlayback`.

```python
# in tests/test_with_golden_fixtures.py

def test_pipeline_with_golden_fixtures(
    whatsapp_fixture,
    playback_client,
    tmp_path: Path,
):
    """Test pipeline with real recorded API responses."""
    process_whatsapp_export(
        ...,
        client=playback_client, # Pass the playback client to the pipeline
    )

    # Assertions to verify the output...
```

### 4. Regenerating Fixtures

If you change the prompts or the logic that generates API requests, you will need to regenerate the fixtures.

1.  **Delete the old fixtures:**
    ```bash
    rm -rf tests/fixtures/golden/api_responses/*
    ```
2.  **Run the recording script again:**
    ```bash
    uv run python scripts/record_golden_fixtures.py ...
    ```
3.  **Commit the new fixtures.**

## Benefits

- **Speed**: Tests run in seconds instead of minutes.
- **Determinism**: Same inputs → same outputs.
- **CI-friendly**: No API keys needed in CI for most tests.
- **Cost**: Zero API costs for most test runs.
- **Debugging**: Easier to debug with reproducible behavior.

## Trade-offs

- **Maintenance**: Fixtures need updating when prompts or the API changes.
- **Storage**: Fixtures add to the repository size.
- **Coverage**: It's important to still have some tests that run against the real API to catch regressions.