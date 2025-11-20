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

---

## Best Practices

### ✅ DO

- **Write E2E tests for every feature.** If it's user-facing, it needs an E2E test.
- **Use mocks for external dependencies.** Keep tests fast and deterministic.
- **Use golden fixtures.** Compare output against known-good files to catch regressions.
- **Clean up.** Use `tmp_path` fixture for all file operations.

### ❌ DON'T

- **Don't add unit tests for internal functions.** Test behavior through the public interface (CLI/Pipeline).
- **Don't make real API calls in standard tests.** Use mocks or VCR.
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
