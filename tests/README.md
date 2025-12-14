# Test Organization

This document explains the test organization strategy in Egregora, helping contributors understand where to place new tests and how to run existing ones.

## New Testing Strategy (2025-01-09)

Egregora has shifted to an **End-to-End (E2E) first testing strategy**. We rely exclusively on E2E tests to validate the entire pipeline, ensuring that the system works correctly from user input to final output.

The `tests/` directory is organized as follows:

```
tests/
├── e2e/              # Full pipeline end-to-end tests (PRIMARY)
├── agents/           # Pydantic-AI agent behavior tests
├── evals/            # LLM output quality evaluations
├── linting/          # Code quality checks
├── utils/            # Testing infrastructure (mocks, VCR adapters)
├── fixtures/         # Test data (WhatsApp exports, golden outputs)
└── conftest.py       # Shared fixtures and configuration
```

**Note:** `unit/` and `integration/` directories have been removed to focus on high-level verification.

### tests/e2e/ - End-to-End Tests

**Characteristics:**
- Full pipeline execution
- Tests complete user workflows (CLI commands, file processing)
- Uses golden fixtures for output validation
- Mocks API calls for determinism and speed
- **This is the primary place for all new functional tests.**

**Examples:**
- `cli/test_write_command.py` - Tests `egregora write` command end-to-end
- `pipeline/test_golden_fixtures.py` - Validates pipeline output against golden files
- `test_extended_e2e.py` - Tests advanced workflows like reader feedback loops

**When to add e2e tests:**
- Adding a new feature or CLI command
- Fixing a bug that spans multiple components
- Ensuring regressions don't break the core workflow

**Running e2e tests:**
```bash
# Run all e2e tests
uv run pytest tests/e2e/

# Run specific test
uv run pytest tests/e2e/cli/test_write_command.py
```

---

### tests/agents/ - Agent Tests

**Characteristics:**
- Tests Pydantic-AI agent behavior in isolation
- Validates tool calling patterns and context handling
- Uses TestModel for deterministic output
- Focuses on "brain" logic without the full pipeline overhead

**Examples:**
- `test_writer_pydantic_agent.py` - Blog post generation agent logic

**When to add agent tests:**
- Developing complex agent prompts or toolchains
- Validating agent reasoning capabilities
- Testing specific agent behaviors that are hard to trigger in E2E

**Running agent tests:**
```bash
uv run pytest tests/agents/
```

---

### tests/evals/ - LLM Quality Evaluations

**Characteristics:**
- Evaluates "soft" quality of LLM outputs (semantic correctness)
- Uses pydantic-evals framework or similar
- Slower, potentially non-deterministic (uses real models)

**When to add evals:**
- Tuning prompts for better writing quality
- Validating that the model "understands" instructions

**Running evals:**
```bash
uv run pytest tests/evals/
```

---

### tests/linting/ - Code Quality Checks

**Characteristics:**
- Static analysis of codebase architecture
- Enforces import rules (e.g., "no pandas in src")
- Validates release requirements

**Running linting tests:**
```bash
uv run pytest tests/linting/
```

---

## Testing Infrastructure

### Shared Fixtures (conftest.py)

We provide shared fixtures to make E2E testing easier:

```python
@pytest.fixture
def whatsapp_fixture() -> WhatsAppFixture:
    """Session-scoped WhatsApp export fixture."""
    ...

@pytest.fixture
def mock_batch_client():
    """Mock Gemini API client for fast, deterministic tests."""
    ...
```

### Mock Utilities (tests/utils/)

- `mock_batch_client.py` - Deterministic Gemini API mocks that simulate LLM responses without network calls. This is crucial for fast E2E tests.
- `pydantic_test_models.py` - ``pydantic-ai`` TestModel classes and embedding stubs that encode expected tool calls directly in code (no VCR cassettes).

### Deterministic LLM fixtures

- ``writer_test_agent`` (from ``tests/conftest.py``) installs a ``WriterTestModel`` that always calls ``write_post_tool`` with predictable metadata and content.
- ``mock_embedding_model`` returns a deterministic hashing-based embedding stub so retrieval tests can run offline.

---

## Best Practices

### ✅ DO

- **Write E2E tests for every feature.** If it's user-facing, it needs an E2E test.
- **Use mocks for external dependencies.** Keep tests fast and deterministic.
- **Use golden fixtures.** Compare output against known-good files to catch regressions.
- **Clean up.** Use `tmp_path` fixture for all file operations.

### ❌ DON'T

- **Don't add unit tests for internal functions.** Test behavior through the public interface (CLI/Pipeline).
- **Don't make real API calls in standard tests.** Use deterministic pydantic-ai TestModels and offline stubs.
- **Don't rely on integration tests.** If components need to work together, test them in an E2E scenario.

---

## Running Tests

```bash
# Run all tests (E2E, Agents, Linting)
uv run pytest tests/

# Run only E2E tests (most common workflow)
uv run pytest tests/e2e/

# Run with coverage
uv run pytest --cov=egregora tests/e2e/
```

---

## Test Configuration Philosophy

We follow the **Fixture/Override Pattern** for test configuration:

1. **Load base configuration** - Use `create_default_config()`
2. **Override infrastructure globally** - Fixtures set tmp_path, test models, disabled slow components
3. **Hardcode specific values only in tests** - Only when testing that specific behavior

### Fixture Selection Guide

| Test Type | Fixture | Use Case |
|-----------|---------|----------|
| **Fast unit tests** | `minimal_config` | No RAG, enrichment, or reader; fast models |
| **Integration tests** | `test_config` | Full config with tmp_path isolation |
| **Pipeline E2E** | `pipeline_test_config` | Optimized for full pipeline runs |
| **RAG tests** | `test_rag_settings_enabled` | RAG enabled with test settings |
| **Reader tests** | `reader_test_config` | Reader agent enabled |
| **Custom needs** | `config_factory(key=val)` | Quick per-test customization |

### Configuration Examples

#### ✅ Good: Using fixtures
```python
def test_something(minimal_config):
    # Config is isolated, uses tmp_path, safe for unit tests
    result = do_something(minimal_config)
    assert result.status == "success"
```

#### ❌ Bad: Direct instantiation
```python
def test_something():
    config = EgregoraConfig()  # WRONG: Uses production defaults!
    result = do_something(config)
```

#### ✅ Good: Customizing via factory
```python
def test_custom_timeout(config_factory):
    config = config_factory(rag__enabled=True, rag__embedding_timeout=0.1)
    # Only the specific values needed for this test are overridden
    assert config.rag.embedding_timeout == 0.1
```

#### ✅ Good: Customizing via model_copy
```python
def test_with_custom_setting(test_config):
    config = test_config.model_copy(deep=True)
    config.pipeline.step_size = 100  # Test-specific override
    result = run_pipeline(config)
```

### Test Configuration Rules

**CRITICAL: Never use production config in tests**

1. **Use fixtures for ALL configuration:**
   - ❌ `config = EgregoraConfig()` (uses production defaults!)
   - ✅ `def test_foo(test_config):` (isolated test config)

2. **Pick the right fixture:**
   - Unit tests: `minimal_config` (fast, RAG/enrichment disabled)
   - Integration: `test_config` (full config, tmp_path)
   - E2E: `pipeline_test_config` (optimized for pipeline)
   - RAG tests: `test_rag_settings_enabled`

3. **Customize via factory or model_copy:**
   ```python
   # Factory (quick)
   config = config_factory(rag__enabled=True, rag__timeout=0.1)

   # model_copy (full control)
   config = test_config.model_copy(deep=True)
   config.pipeline.step_size = 100
   ```

4. **Infrastructure must use tmp_path:**
   - ❌ `db_path = Path(".egregora/db.duckdb")`
   - ✅ `db_path = tmp_path / "test.duckdb"`

For complete fixture documentation, see `tests/conftest.py`.

---

## Troubleshooting

### Test fails with "production config" error

You're likely using `EgregoraConfig()` directly. Use a fixture instead:

```python
# Before
def test_something():
    config = EgregoraConfig()  # ❌

# After
def test_something(minimal_config):  # ✅
    config = minimal_config
```

### Test fails with path not found

Ensure you're using `tmp_path` for all file operations:

```python
# Before
db_path = Path(".egregora/test.db")  # ❌

# After
def test_something(tmp_path):
    db_path = tmp_path / "test.db"  # ✅
```

### RAG tests fail

Make sure to use `test_rag_settings_enabled` if you need RAG:

```python
def test_rag_feature(test_rag_settings_enabled):
    # RAG is now enabled
```
