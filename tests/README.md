# Test Organization

This document explains the test organization strategy in Egregora, helping contributors understand where to place new tests and how to run existing ones.

## Test Categories

Egregora uses a **layered testing strategy** with tests organized by scope and dependencies:

```
tests/
├── unit/              # Pure unit tests (9 files)
├── integration/       # Database & API integration tests (7 files)
├── e2e/              # Full pipeline end-to-end tests (5 files)
├── agents/           # Pydantic-AI agent behavior tests (4 files)
├── evals/            # LLM output quality evaluations (1 file)
├── linting/          # Code quality checks (4 files)
├── utils/            # Testing infrastructure (mocks, VCR adapters)
├── fixtures/         # Test data (WhatsApp exports, golden outputs)
└── conftest.py       # Shared fixtures and configuration
```

### tests/unit/ - Pure Unit Tests

**Characteristics:**
- No external I/O (no files, databases, or API calls)
- Fast execution (milliseconds per test)
- Pure functions and business logic
- Deterministic and isolated

**Examples:**
- `test_anonymizer.py` - UUID generation and name anonymization
- `test_schema.py` - Table schema validation
- `test_message_id_timezone_independence.py` - Timestamp handling logic

**When to add unit tests:**
- Testing pure functions with deterministic outputs
- Validating data transformations (Ibis table operations)
- Testing business logic without side effects
- Verifying schema contracts

**Running unit tests:**
```bash
# Run all unit tests
uv run pytest tests/unit/

# Run specific test file
uv run pytest tests/unit/test_anonymizer.py

# Run specific test function
uv run pytest tests/unit/test_anonymizer.py::test_anonymize_table

# With verbose output
uv run pytest tests/unit/ -v
```

---

### tests/integration/ - Integration Tests

**Characteristics:**
- Uses DuckDB database operations
- Exercises component interactions
- Prefers deterministic doubles over live Gemini calls (TestModel and mock embeddings)
- Limited legacy tests still reference existing VCR cassettes

**Examples:**
- `test_rag_store.py` - Vector store operations with DuckDB VSS
- `test_annotations_store.py` - Database persistence layer
- `test_enrichment_avatars.py` - Avatar download with API calls

**When to add integration tests:**
- Testing database queries and persistence
- Validating DuckDB extensions (VSS, Parquet)
- Testing API client behavior
- Verifying component integration points

**Running integration tests:**
```bash
# Run all integration tests
uv run pytest tests/integration/

# Use exact mode to avoid VSS extension dependency
uv run pytest tests/integration/ --retrieval-mode=exact
```

---

### tests/e2e/ - End-to-End Tests

**Characteristics:**
- Full pipeline execution
- Tests complete user workflows
- Uses golden fixtures for output validation
- Mocks API calls for determinism

**Examples:**
- `test_with_golden_fixtures.py` - Full pipeline with Pydantic TestModel
- `test_whatsapp_real_scenario.py` - Real WhatsApp export processing
- `test_stage_commands.py` - CLI command integration

**When to add e2e tests:**
- Testing complete user workflows (ingestion → publication)
- Validating CLI commands end-to-end
- Ensuring pipeline stages work together correctly
- Regression testing with golden outputs

**Running e2e tests:**
```bash
# Run all e2e tests
uv run pytest tests/e2e/

# Run with golden fixture validation
uv run pytest tests/e2e/test_with_golden_fixtures.py

# Fast mock-based e2e test
uv run pytest tests/e2e/test_fast_with_mock.py
```

---

### tests/agents/ - Agent Tests

**Characteristics:**
- Tests Pydantic-AI agent behavior
- Validates tool calling and context handling
- Uses TestModel for deterministic output
- Focuses on agent orchestration logic

**Examples:**
- `test_writer_pydantic_agent.py` - Blog post generation agent
- `test_editor_pydantic_agent.py` - Interactive post refinement
- `test_ranking_pydantic_agent.py` - Elo ranking agent

**When to add agent tests:**
- Testing agent tool registration and invocation
- Validating agent context passing
- Testing agent prompt handling
- Verifying structured output generation

**Running agent tests:**
```bash
# Run all agent tests
uv run pytest tests/agents/

# Run specific agent test
uv run pytest tests/agents/test_writer_pydantic_agent.py

# With Pydantic-AI debug output
uv run pytest tests/agents/ -v --log-cli-level=DEBUG
```

---

### tests/evals/ - LLM Quality Evaluations

**Characteristics:**
- Evaluates LLM output quality
- Uses pydantic-evals framework
- Tests semantic correctness, not exact matches
- Slower than other test types

**Examples:**
- `test_writer_with_evals.py` - Writer agent output quality
- `writer_evals.py` - Evaluation datasets and criteria

**When to add evals:**
- Testing LLM output quality metrics
- Validating semantic correctness of generated content
- A/B testing different prompts or models
- Regression testing for content quality

**Running evals:**
```bash
# Run all evals
uv run pytest tests/evals/

# Run with detailed output
uv run pytest tests/evals/ -v -s
```

---

### tests/linting/ - Code Quality Checks

**Characteristics:**
- Static analysis of codebase
- Enforces architecture rules
- Tests import policies
- Validates release requirements

**Examples:**
- `test_banned_imports.py` - Enforces Ibis-first, no pandas in src/
- `test_absolute_imports.py` - Ensures absolute imports
- `test_release_checks.py` - Validates version and changelog

**When to add linting tests:**
- Enforcing new architectural rules
- Preventing dependency creep
- Validating code style requirements
- Ensuring release quality standards

**Running linting tests:**
```bash
# Run all linting tests
uv run pytest tests/linting/

# Check import policy compliance
uv run pytest tests/linting/test_banned_imports.py
```

---

## Deterministic LLM + Embedding Strategy

Tests now avoid recording new VCR cassettes. Instead, they rely on deterministic doubles for both LLM calls and embeddings so the suite can run offline and stay stable when prompts evolve.

### LLM behavior via `TestModel`

- Agent tests and end-to-end flows stub `GeminiModel` with `pydantic_ai.models.test.TestModel`.
- Use a subclass when you need scripted tool arguments or fixed content. Example: `GoldenTestModel` in `tests/e2e/test_with_golden_fixtures.py` wires explicit tool payloads to keep the writer pipeline deterministic.
- Expected behavior: the same prompt and seed always yield the same tool calls and text, making golden fixtures reproducible.
- Choose `TestModel` when validating agent orchestration, tool wiring, or prompt shaping without hitting the network.

### Embedding and client mocks

- Embedding and `genai.Client` interactions are replaced by `MockGeminiBatchClient` / `MockGeminiClient` from `tests/utils/mock_batch_client.py`.
- The `mock_batch_client` fixture monkeypatches Gemini clients globally so embedding vectors and content responses are generated locally and deterministically.
- Expected behavior: identical text produces identical vectors (deterministic MD5 seeding), enabling stable similarity assertions; mock content generation returns structured text with predictable headers for downstream parsing.
- Choose these mocks when a test touches embeddings, batch prompts, or file uploads but should remain offline.

### Updating mocks when prompts change

- If you adjust a prompt or tool signature, update the scripted outputs in the relevant `TestModel` subclass (e.g., `GoldenTestModel`) so tool arguments match the new contract.
- For embedding-dependent logic, refresh expectations in tests and, if needed, tweak `MockGeminiBatchClient.generate_content` or response text to mirror the new prompt shape.
- Rerun the affected tests to confirm deterministic behavior—no cassette re-recording is needed. Legacy VCR cassettes remain for historical coverage but should not require updates unless explicitly touched.

---

## Running Tests

### Quick Commands

```bash
# Run all tests
uv run pytest tests/

# Run by category
uv run pytest tests/unit/              # Unit tests only
uv run pytest tests/integration/       # Integration tests only
uv run pytest tests/agents/            # Agent tests only

# Run specific test
uv run pytest tests/unit/test_anonymizer.py::test_anonymize_table

# With coverage
uv run pytest --cov=egregora --cov-report=html tests/

# Fast mode (skip slow tests)
uv run pytest -m "not slow" tests/

# Verbose output
uv run pytest tests/ -v

# Show print statements
uv run pytest tests/ -s

# Stop on first failure
uv run pytest tests/ -x
```

### Test Markers

```bash
# Skip slow tests
uv run pytest -m "not slow" tests/

# Run only integration tests
uv run pytest -m integration tests/

# Run only agent tests
uv run pytest -m agent tests/
```

### Environment Variables

```bash
# Required for API calls (first run)
export GOOGLE_API_KEY="your-api-key"

# Use exact retrieval mode (no VSS extension)
uv run pytest tests/ --retrieval-mode=exact

# Use Pydantic-AI backend
export EGREGORA_LLM_BACKEND="pydantic-ai"
```

---

## Adding New Tests

### Decision Tree: Where Should This Test Go?

```
Does it call external services (API, database)?
├─ NO → Is it testing pure business logic?
│       └─ YES → tests/unit/
│
├─ YES → Does it test a full user workflow?
│       ├─ YES → tests/e2e/
│       │
│       └─ NO → Is it testing a Pydantic-AI agent?
│               ├─ YES → tests/agents/
│               │
│               └─ NO → Does it use DuckDB or API calls?
│                       └─ YES → tests/integration/
```

### Quick Reference Table

| Test Type | No I/O | Uses DB | Uses API | Full Pipeline | Test Scope |
|-----------|--------|---------|----------|---------------|------------|
| **Unit** | ✅ | ❌ | ❌ | ❌ | Single function/class |
| **Integration** | ❌ | ✅ | ✅ | ❌ | Component interactions |
| **E2E** | ❌ | ✅ | ✅ (mocked) | ✅ | Complete workflows |
| **Agents** | ❌ | ✅ | ✅ (mocked) | ❌ | Pydantic-AI agents |
| **Evals** | ❌ | ✅ | ✅ (real) | ❌ | LLM quality metrics |
| **Linting** | ✅ | ❌ | ❌ | ❌ | Static analysis |

### Example: Adding a New Unit Test

```python
# tests/unit/test_my_feature.py

import ibis
from egregora.my_module import my_pure_function

def test_my_pure_function():
    """Test pure business logic with no I/O."""
    # Arrange
    data = {"column": [1, 2, 3]}
    table = ibis.memtable(data)

    # Act
    result = my_pure_function(table)

    # Assert
    assert result.execute()["column"].tolist() == [2, 4, 6]
```

### Example: Adding a New Integration Test

```python
# tests/integration/test_my_store.py

import pytest

def test_my_store_persistence(tmp_path):
    """Test database persistence with DuckDB."""
    store_path = tmp_path / "test.db"

    # Create store and save data
    store = MyStore(store_path)
    store.save({"key": "value"})

    # Load from disk
    loaded = store.load()
    assert loaded["key"] == "value"
```

### Example: Adding a New E2E Test

```python
# tests/e2e/test_my_workflow.py

def test_complete_workflow(whatsapp_fixture, tmp_path, mock_batch_client):
    """Test full pipeline workflow with mocked API."""
    output_dir = tmp_path / "output"

    # Run complete pipeline
    process_whatsapp_export(
        zip_path=whatsapp_fixture.zip_path,
        output_dir=output_dir,
        enable_enrichment=False,
    )

    # Verify output artifacts
    assert (output_dir / "docs" / "posts").exists()
    assert list((output_dir / "docs" / "posts").glob("*.md"))
```

---

## Golden Fixtures

End-to-end tests use **golden fixtures** to validate pipeline output against known-good results.

### Golden Fixture Location

```
tests/fixtures/golden/
└── expected_output/
    ├── posts/
    ├── profiles/
    └── mkdocs.yml
```

### Using Golden Fixtures

```python
def test_with_golden_comparison(whatsapp_fixture, tmp_path):
    """Compare pipeline output to golden fixtures."""
    # Run pipeline
    process_whatsapp_export(...)

    # Load golden fixture
    golden_path = Path("tests/fixtures/golden/expected_output")

    # Compare outputs
    assert_files_match(output_dir, golden_path)
```

### Updating Golden Fixtures

When intentionally changing pipeline behavior:

```bash
# 1. Delete old golden output
rm -rf tests/fixtures/golden/expected_output/

# 2. Run test to generate new output
uv run pytest tests/e2e/test_with_golden_fixtures.py

# 3. Manually verify new output is correct

# 4. Copy new output to golden fixtures
cp -r /tmp/test_output/ tests/fixtures/golden/expected_output/

# 5. Commit updated golden fixtures
git add tests/fixtures/golden/
git commit -m "test: Update golden fixtures for new behavior"
```

---

## Testing Infrastructure

### Shared Fixtures (conftest.py)

```python
@pytest.fixture
def whatsapp_fixture() -> WhatsAppFixture:
    """Session-scoped WhatsApp export fixture."""
    ...

@pytest.fixture
def mock_batch_client():
    """Mock Gemini API client for fast tests."""
    ...

@pytest.fixture
def vcr_config():
    """Legacy VCR configuration (kept for existing cassettes, avoid new recordings)."""
    ...
```

### Mock Utilities (tests/utils/)

- `mock_batch_client.py` - Deterministic Gemini API mocks
- `raw_gemini_client.py` - Real client wrapper for integration tests
- `vcr_adapter.py` - Legacy VCR HTTP recording adapter (do not use for new tests)

### Test Data (tests/fixtures/)

- `Conversa do WhatsApp com Teste.zip` - Sample WhatsApp export
- `golden/` - Expected pipeline outputs for regression testing

---

## CI/CD Considerations

### GitHub Actions

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    uv run pytest tests/ \
      --cov=egregora \
      --retrieval-mode=exact \
      -m "not slow"
```

### Pre-commit Hooks

```bash
# Run linting tests before commit
uv run pytest tests/linting/
```

### Coverage Reports

```bash
# Generate HTML coverage report
uv run pytest --cov=egregora --cov-report=html tests/

# View report
open htmlcov/index.html
```

---

## Best Practices

### ✅ DO

- **Write unit tests first** - They're fastest and catch most bugs
- **Use mocks for external dependencies** - Faster and more deterministic
- **Keep tests isolated** - Each test should clean up after itself
- **Use descriptive test names** - `test_anonymize_preserves_message_content`
- **Test edge cases** - Empty inputs, nulls, boundary values
- **Update golden fixtures intentionally** - Document why output changed

### ❌ DON'T

- **Don't test implementation details** - Test behavior, not internals
- **Don't share state between tests** - Use fixtures for setup
- **Don't skip tests without reason** - Fix or remove failing tests
- **Don't commit without running tests** - Use pre-commit hooks
- **Don't make real API calls in tests** - Use deterministic mocks
- **Don't ignore flaky tests** - Fix root causes

---

## Common Issues

### DuckDB VSS Extension Not Available

**Problem**: Tests fail with "VSS extension not found"

**Solution**: Use exact retrieval mode
```bash
uv run pytest tests/ --retrieval-mode=exact
```

### Mock Output Drift

**Problem**: A test fails because scripted `TestModel` output or mock response no longer matches the prompt.

**Solution**: Update the relevant deterministic mock instead of re-recording traffic.
```bash
# Adjust the scripted tool args/text in the appropriate TestModel subclass
uv run pytest tests/e2e/test_with_golden_fixtures.py

# Or tweak MockGeminiBatchClient.generate_content/mock embeddings if shape changed
uv run pytest tests/e2e/test_fast_with_mock.py
```

### Missing GOOGLE_API_KEY

**Problem**: Integration test fails with API key error

**Solution**: Most tests use mocks and don't need API keys. For tests that do:
```bash
export GOOGLE_API_KEY="your-api-key"
uv run pytest tests/integration/
```

### Test Hangs or Times Out

**Problem**: Test runs indefinitely

**Solution**: Use pytest timeout plugin
```bash
uv add --dev pytest-timeout
uv run pytest tests/ --timeout=30
```

---

## Further Reading

- [pytest Documentation](https://docs.pytest.org/)
- [Pydantic-AI Testing](https://ai.pydantic.dev/testing/) - Agent test utilities
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contributor guidelines
- [CLAUDE.md](../CLAUDE.md) - Project architecture and conventions
