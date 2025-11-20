# Testing

Egregora uses pytest for testing; recorded HTTP cassettes are no longer maintained.

## Running Tests

### All Tests

```bash
uv run pytest tests/
```

### Specific Test File

```bash
uv run pytest tests/test_parser.py
```

### With Coverage

```bash
uv run pytest --cov=egregora --cov-report=html tests/
```

### Verbose Output

```bash
uv run pytest -v tests/
```

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures
├── test_parser.py                   # Ingestion tests
├── test_anonymizer.py               # Privacy tests
├── test_enrichment.py               # Augmentation tests
├── test_rag.py                      # Knowledge tests
├── test_writer.py                   # Generation tests
├── test_integration.py              # End-to-end tests
├── test_gemini_dispatcher.py        # API dispatcher tests
├── test_with_golden_fixtures.py     # Integration tests with golden fixtures
└── fixtures/
    ├── vcr_cassettes/               # Recorded API responses
    ├── sample_chats/                # Test WhatsApp exports
    └── golden/                      # Golden test data
```

## Test Categories

### Unit Tests

Test individual functions and classes in isolation:

```python
def test_anonymize_author():
    """Test that author names are properly anonymized."""
    from egregora.privacy import anonymize_author

    result = anonymize_author("John Doe")

    assert len(result) == 8
    assert result.isalnum()
    # Same input → same output
    assert anonymize_author("John Doe") == result
```

### Integration Tests

Test multiple components working together:

```python
def test_full_pipeline():
    """Test complete pipeline from export to posts."""
    from egregora.orchestration import run_pipeline

    run_pipeline(
        export_path="tests/fixtures/sample_chat.zip",
        output_dir=tmp_path,
        api_key=os.getenv("GOOGLE_API_KEY")
    )

    posts = list((tmp_path / "docs/posts").glob("*.md"))
    assert len(posts) > 0
```

### Live API Tests

Use mocks whenever possible. When a live Gemini call is unavoidable, set `GOOGLE_API_KEY` and avoid recording HTTP responses. The `tests/cassettes/` directory should remain empty.

## Fixtures

### Common Fixtures

Defined in `conftest.py`:

```python
@pytest.fixture
def sample_messages():
    """Sample conversation DataFrame."""
    return ibis.memtable([
        {
            "timestamp": datetime(2025, 1, 1, 10, 0),
            "author": "Alice",
            "message": "Hello world"
        }
    ])

@pytest.fixture
def gemini_client():
    """Google Gemini client."""
    api_key = os.getenv("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key)
```

### Using Fixtures

```python
def test_with_fixture(sample_messages):
    """Test using a fixture."""
    df = sample_messages
    assert len(df) == 1
```

## Live API Guidance

Recorded HTTP cassettes are no longer kept. Prefer mocks for external services, and only hit live Gemini APIs when `GOOGLE_API_KEY` is available. Remove any generated cassette files.

## Test Data

### Sample WhatsApp Exports

Located in `tests/fixtures/sample_chats/`:

```
sample_chats/
├── basic_chat.zip           # Minimal chat
├── multiday_chat.zip        # Multiple days
└── media_references.zip     # With media refs
```

### Golden Fixtures

Golden test data for regression testing:

```python
def test_against_golden():
    """Test output matches golden reference."""
    result = process_data(input)
    expected = load_golden("expected_output.json")
    assert result == expected
```

## Mocking

### Mock External Services

```python
from unittest.mock import patch, MagicMock

def test_with_mock():
    """Test with mocked Gemini client."""
    mock_client = MagicMock()
    mock_client.embed_text.return_value = [0.1] * 768

    result = embed_text("test", mock_client)
    assert len(result) == 768
```

### Mock File System

```python
def test_file_operations(tmp_path):
    """Test using temporary directory."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    result = read_file(test_file)
    assert result == "content"
```

## Parametrized Tests

Test multiple cases efficiently:

```python
@pytest.mark.parametrize("input,expected", [
    ("Alice", "a3f2b91c"),
    ("Bob", "b7e4d23a"),
    ("Charlie", "c9d1e5f7"),
])
def test_anonymization(input, expected):
    """Test anonymization with multiple inputs."""
    result = anonymize_author(input)
    assert result == expected
```

## Test Coverage

### Generate Coverage Report

```bash
uv run pytest --cov=egregora --cov-report=html tests/
open htmlcov/index.html
```

### Coverage Goals

- **Core modules**: 90%+ coverage
- **Utilities**: 80%+ coverage
- **CLI**: 70%+ coverage (harder to test)

## Continuous Integration

Tests run automatically on GitHub Actions:

- Every push
- Every pull request
- Nightly (full test suite)

### Local CI Simulation

```bash
# Run what CI runs
uv run pytest tests/
uv run ruff check src/
uv run black --check src/
```

## Debugging Tests

### Print Debug Info

```python
def test_with_debug(capfd):
    """Test with captured output."""
    print("Debug info")
    result = function_under_test()

    out, err = capfd.readouterr()
    assert "Debug info" in out
```

### Use pytest debugger

```bash
# Drop into debugger on failure
uv run pytest --pdb tests/

# Drop into debugger on first failure
uv run pytest -x --pdb tests/
```

### VSCode Debug Configuration

```json
{
  "name": "Pytest: Current File",
  "type": "python",
  "request": "launch",
  "module": "pytest",
  "args": ["${file}", "-v"],
  "console": "integratedTerminal"
}
```

## Best Practices

1. **Arrange-Act-Assert**: Structure tests clearly
2. **One assertion per test**: Keep tests focused
3. **Descriptive names**: `test_parser_handles_multiline_messages`
4. **Use fixtures**: Share setup code
5. **Mock external calls**: Prefer mocks; use live APIs explicitly when required
6. **Clean up**: Use `tmp_path` for file tests
7. **Test edge cases**: Empty inputs, null values, errors

## See Also

- [Contributing Guide](contributing.md) - Development workflow
- [Project Structure](structure.md) - Codebase organization
